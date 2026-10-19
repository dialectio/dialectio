"""Speaker tests: a member proves they speak a language (later also a dialect).

The test is TEST_CARDS control cards of one variety, at least PASS_MARK right ("don't know"
counts as wrong). Words are the variety's checked words. A trap shows a word with the meaning
of a word spelled like it ("вечір" with the meaning of "вечеря"), which someone guessing falls
for more often than a speaker. When the test's language is the interface language, the meaning
is the concept's description, not a word: "вечір: вечір?" would give the answer away.

One attempt per variety per day; the answers also count as control answers of the language,
so a member who passed needs no quiz. Dialects get a test once they have DIALECT_MIN_WORDS
checked words; languages need LANGUAGE_MIN_WORDS.
"""

import hashlib
import hmac
import random
import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.accounts import current_user, require_member
from app.api.gold import voter_hash
from app.api.lexicon import UNVERIFIED_SOURCES, SessionDep
from app.config import settings
from app.models import GoldAnswer, MemberVariety, SpeakerTest

router = APIRouter(prefix="/api/speaker", tags=["accounts"])

TEST_CARDS = 12
PASS_MARK = 11
RETRY_AFTER = timedelta(days=1)
TEST_MINUTES = 30
LANGUAGE_MIN_WORDS = 100
DIALECT_MIN_WORDS = 20
MIN_DESCRIPTION = 15  # shorter descriptions ("body part") are too vague to test with
LOCALE_LANGUAGES = {"uk": "ukr", "en": "eng", "pl": "pol", "de": "deu", "es": "spa", "fr": "fra"}

# The concept's description in the interface language
DESCRIPTION = """CASE :locale WHEN 'uk' THEN c.description_uk WHEN 'en' THEN c.description_en
                 ELSE c.descriptions ->> :locale END"""
CHECKED = """f.is_primary AND f.status = 'approved'
             AND (src.name IS NULL OR NOT (src.name = ANY(:unverified_sources)))"""

TESTABLE = text(f"""
    SELECT v.code, v.kind, v.name_en, v.name_uk, v.names, count(*) AS words
    FROM form f
    JOIN variety v ON v.id = f.variety_id AND v.kind IN ('language', 'dialect')
    JOIN concept c ON c.id = f.concept_id AND c.slug IS NOT NULL
    LEFT JOIN source src ON src.id = f.source_id
    WHERE {CHECKED}
    GROUP BY v.id
    HAVING count(*) >= CASE v.kind WHEN 'dialect' THEN :dialect_min ELSE :language_min END
    ORDER BY count(*) DESC
""")

TEST_WORDS = text(f"""
    SELECT f.spelling, c.id AS concept_id, {DESCRIPTION} AS description
    FROM form f
    JOIN variety v ON v.id = f.variety_id AND v.code = :variety
    JOIN concept c ON c.id = f.concept_id AND c.slug IS NOT NULL
    LEFT JOIN source src ON src.id = f.source_id
    WHERE {CHECKED}
      AND (NOT :describe OR length({DESCRIPTION}) >= :min_description)
    ORDER BY random()
    LIMIT :limit
""")

# Concepts for a trap: those whose word is spelled most like the card's word first; never
# one the card's word also means (homonyms), nor one described the same way
TRAPS = text(f"""
    SELECT c.id, similarity(search_key(f.spelling), search_key(:spelling)) AS likeness
    FROM form f
    JOIN variety v ON v.id = f.variety_id AND v.code = :variety
    JOIN concept c ON c.id = f.concept_id AND c.slug IS NOT NULL
    WHERE f.is_primary AND f.status = 'approved' AND c.id <> :concept_id
      AND (search_key(f.spelling) % search_key(:spelling) OR f.id % 97 = :salt)
      AND NOT EXISTS (SELECT 1 FROM form g WHERE g.concept_id = c.id
                      AND g.variety_id = f.variety_id AND lower(g.spelling) = lower(:spelling))
      AND (NOT :describe OR (length({DESCRIPTION}) >= :min_description
                             AND {DESCRIPTION} IS DISTINCT FROM :description))
    ORDER BY likeness DESC
    LIMIT 5
""")

MEANING = text(f"""
    SELECT c.gloss_en, c.gloss_uk, c.glosses ->> :locale AS gloss, {DESCRIPTION} AS description
    FROM concept c WHERE c.id = :concept_id
""")


class TestableVariety(BaseModel):
    code: str
    kind: str
    name_en: str
    name_uk: str | None
    names: dict[str, str] = {}
    words: int
    # For a signed-in member
    speaks: bool = False  # said so in the profile
    tested: bool = False  # passed the test
    retry_after: int | None = None


class SpeakerCard(BaseModel):
    index: int
    spelling: str
    meaning: str
    described: bool  # the meaning is a description, not a word
    token: str


class TestOut(BaseModel):
    id: int | None = None
    cards: list[SpeakerCard] = []
    pass_mark: int = PASS_MARK
    # Seconds until the member may try again after a failed attempt (no cards meanwhile)
    retry_after: int | None = None


class TestIn(BaseModel):
    variety: str = Field(max_length=40)
    locale: str = Field(pattern="^(uk|en|pl|de|es|fr)$")


class AnswerIn(BaseModel):
    token: str = Field(max_length=60)
    value: int = Field(ge=-1, le=1)  # 0 = "don't know": wrong in a test


class AnswerOut(BaseModel):
    correct: bool
    answered: int
    score: int
    finished: bool
    passed: bool | None


class SpeaksIn(BaseModel):
    variety: str = Field(max_length=40)
    speaks: bool


def root(variety: str) -> str:
    return variety.split("-")[0]


def sign(test_id: int, index: int, expected: int) -> str:
    message = f"speaker|{test_id}|{index}|{expected}".encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()[:24]


def read_token(test_id: int, token: str) -> tuple[int, int] | None:
    """(card index, expected answer) of a genuine token of this test, else None."""
    try:
        index_text, signature = token.split(".")
        index = int(index_text)
    except ValueError:
        return None
    for expected in (1, -1):
        if hmac.compare_digest(signature, sign(test_id, index, expected)):
            return index, expected
    return None


def is_speaker(session: Session, user_id: int, variety: str) -> bool:
    """Whether the member passed the test of this variety or of its language."""
    return bool(
        session.scalar(
            select(MemberVariety.user_id).where(
                MemberVariety.user_id == user_id,
                MemberVariety.variety_code.in_({variety, root(variety)}),
                MemberVariety.tested_at.is_not(None),
            )
        )
    )


def retry_after(session: Session, user_id: int, variety: str) -> int | None:
    """Seconds left until the next attempt, if the last one (within a day) was not passed."""
    started = session.scalar(
        select(SpeakerTest.started_at)
        .where(
            SpeakerTest.user_id == user_id,
            SpeakerTest.variety_code == variety,
            SpeakerTest.passed.is_not(True),
        )
        .order_by(SpeakerTest.started_at.desc())
        .limit(1)
    )
    if started is None:
        return None
    wait = (started + RETRY_AFTER - datetime.now(UTC)).total_seconds()
    return int(wait) if wait > 0 else None


def meaning_of(session: Session, concept_id: int, locale: str, describe: bool) -> str:
    row = session.execute(MEANING, {"concept_id": concept_id, "locale": locale}).mappings().one()
    if describe:
        return row["description"]
    if locale == "uk":
        return row["gloss_uk"] or row["gloss_en"]
    return row["gloss"] or row["gloss_en"]


def same_meaning(a: str, b: str) -> bool:
    """Whether two meanings are the same words, leaving out hints in brackets."""

    def core(meaning: str) -> str:
        return re.sub(r"\s*\(.*?\)", "", meaning).strip().casefold()

    return core(a) == core(b)


def test_cards(session: Session, test_id: int, variety: str, locale: str) -> list[SpeakerCard]:
    describe = root(variety) == LOCALE_LANGUAGES[locale]
    params = {
        "variety": variety,
        "locale": locale,
        "describe": describe,
        "min_description": MIN_DESCRIPTION,
        "unverified_sources": list(UNVERIFIED_SOURCES),
    }
    words = session.execute(TEST_WORDS, {**params, "limit": TEST_CARDS}).mappings().all()
    # About half the cards are traps, never all of one kind
    truthful = [i < TEST_CARDS // 2 + random.choice((-1, 0, 1)) for i in range(len(words))]  # noqa: S311
    random.shuffle(truthful)
    cards = []
    for word, true in zip(words, truthful, strict=True):
        meaning = meaning_of(session, word["concept_id"], locale, describe)
        if not true:
            traps = session.execute(
                TRAPS,
                {
                    **params,
                    "spelling": word["spelling"],
                    "concept_id": word["concept_id"],
                    "description": word["description"],
                    "salt": random.randrange(97),  # noqa: S311 (some unlike words to pick from)
                },
            ).all()
            random.shuffle(traps)
            # Not a concept named like the real one ("agreement" and "agreement (contract)")
            others = (meaning_of(session, trap.id, locale, describe) for trap in traps)
            trap = next((m for m in others if not same_meaning(m, meaning)), None)
            if trap is None:
                true = True
            else:
                meaning = trap
        index = len(cards)
        cards.append(
            SpeakerCard(
                index=index,
                spelling=word["spelling"],
                meaning=meaning,
                described=describe,
                token=f"{index}.{sign(test_id, index, 1 if true else -1)}",
            )
        )
    return cards


@router.get("/varieties")
def testable_varieties(request: Request, session: SessionDep) -> list[TestableVariety]:
    """Languages and dialects with a test, with the signed-in member's state in each."""
    rows = session.execute(
        TESTABLE,
        {
            "unverified_sources": list(UNVERIFIED_SOURCES),
            "language_min": LANGUAGE_MIN_WORDS,
            "dialect_min": DIALECT_MIN_WORDS,
        },
    ).mappings()
    varieties = [TestableVariety(**row) for row in rows]
    user = current_user(request, session)
    if user is None:
        return varieties
    mine = {
        row.variety_code: row.tested_at
        for row in session.execute(
            select(MemberVariety.variety_code, MemberVariety.tested_at).where(
                MemberVariety.user_id == user.id
            )
        )
    }
    for variety in varieties:
        if variety.code in mine:
            variety.speaks = True
            variety.tested = mine[variety.code] is not None
        if not variety.tested:
            variety.retry_after = retry_after(session, user.id, variety.code)
    return varieties


@router.post("/tests")
def start_test(data: TestIn, request: Request, session: SessionDep) -> TestOut:
    user = require_member(request, session)
    tested = session.scalar(
        select(MemberVariety.tested_at).where(
            MemberVariety.user_id == user.id, MemberVariety.variety_code == data.variety
        )
    )
    if tested is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_speaker")
    wait = retry_after(session, user.id, data.variety)
    if wait:
        return TestOut(retry_after=wait)
    test = SpeakerTest(user_id=user.id, variety_code=data.variety, cards=TEST_CARDS)
    session.add(test)
    session.flush()
    cards = test_cards(session, test.id, data.variety, data.locale)
    if len(cards) < TEST_CARDS:
        session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "not_testable")
    session.commit()
    return TestOut(id=test.id, cards=cards)


@router.post("/tests/{test_id}/answers")
def answer(test_id: int, data: AnswerIn, request: Request, session: SessionDep) -> AnswerOut:
    user = require_member(request, session)
    test = session.get(SpeakerTest, test_id, with_for_update=True)
    if test is None or test.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_test")
    if test.passed is not None or datetime.now(UTC) - test.started_at > timedelta(
        minutes=TEST_MINUTES
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "test_over")
    parsed = read_token(test.id, data.token)
    if parsed is None or not 0 <= parsed[0] < test.cards or test.answered >> parsed[0] & 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown_or_used_card")
    index, expected = parsed
    correct = data.value == expected
    test.answered |= 1 << index
    test.correct += correct
    if data.value != 0:
        # Like any control answer: a member who passed has passed the quiz too
        session.add(
            GoldAnswer(
                voter=voter_hash(f"user:{user.id}"),
                language=root(test.variety_code),
                correct=correct,
            )
        )
    answered = test.answered.bit_count()
    if answered == test.cards:
        test.passed = test.correct >= PASS_MARK
        if test.passed:
            now = datetime.now(UTC)
            session.execute(
                insert(MemberVariety)
                .values(user_id=user.id, variety_code=test.variety_code, tested_at=now)
                .on_conflict_do_update(
                    index_elements=["user_id", "variety_code"], set_={"tested_at": now}
                )
            )
    session.commit()
    return AnswerOut(
        correct=correct,
        answered=answered,
        score=test.correct,
        finished=test.passed is not None,
        passed=test.passed,
    )


@router.put("/speaks", status_code=status.HTTP_204_NO_CONTENT)
def set_speaks(data: SpeaksIn, request: Request, session: SessionDep) -> None:
    """Say in the profile that one speaks a language or dialect, or take it back (a passed
    test goes with it)."""
    user = require_member(request, session)
    if data.speaks:
        session.execute(
            insert(MemberVariety)
            .values(user_id=user.id, variety_code=data.variety)
            .on_conflict_do_nothing()
        )
    else:
        session.execute(
            delete(MemberVariety).where(
                MemberVariety.user_id == user.id, MemberVariety.variety_code == data.variety
            )
        )
    session.commit()
