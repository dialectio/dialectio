"""Control cards: words with a known answer, to check voters without accounts.

A control card is either a checked word shown with its own meaning (the answer is "yes") or
a trap: a real word of the language shown with another concept's meaning ("no"). Guests
answer three of them (the quiz) before their votes on a language count, and the game mixes
them in among the real cards, so a voter who starts clicking at random stops counting.

The card carries a token with a random nonce and the language, signed for the expected
answer: the browser can't tell the answer from it, the server checks the signature against
both answers. A token can be answered once.
"""

import hashlib
import hmac
import random
import secrets
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.lexicon import UNVERIFIED_SOURCES, SessionDep
from app.config import settings
from app.models import GoldAnswer

router = APIRouter(prefix="/api/check", tags=["feedback"])

QUIZ_CARDS = 3
PASS_CORRECT = 2  # of a voter's last QUIZ_CARDS answers in a language
RETRY_AFTER = timedelta(days=1)  # after a failed quiz
LANGUAGE = r"^[a-z]{3}$"
_used_nonces: OrderedDict[str, None] = OrderedDict()
USED_NONCES_KEPT = 100_000


class GoldCard(BaseModel):
    """Looks like a game card; `gold` is the token the answer goes back with."""

    form_id: int  # negative: not a real form id, the card can't be voted on as a word
    spelling: str
    variety_code: str
    kind: str
    variety_name_en: str
    variety_name_uk: str | None
    variety_names: dict[str, str] = {}
    slug: str
    gloss_en: str
    gloss_uk: str | None
    glosses: dict[str, str] = {}
    standard: str | None
    english: str | None
    region_codes: list[str]
    votes: int = 0
    gold: str


class QuizOut(BaseModel):
    cards: list[GoldCard]
    # Seconds until a voter who failed may try again; the cards are empty meanwhile
    retry_after: int | None = None


class QuizStatus(BaseModel):
    passed: bool
    retry_after: int | None = None


class GoldIn(BaseModel):
    voter: str = Field(min_length=8, max_length=64)
    token: str = Field(max_length=200)
    value: int = Field(ge=-1, le=1)  # 0 = "don't know": not counted


class GoldResult(BaseModel):
    correct: bool | None  # None for "don't know"
    passed: bool


# Checked words of a language (or its dialects): approved, from a trusted source, the
# variety's main word for a concept that has a page
CHECKED_WORDS = text("""
    SELECT f.spelling, f.concept_id, v.code AS variety_code, v.kind,
           v.name_en AS variety_name_en, v.name_uk AS variety_name_uk,
           v.names AS variety_names,
           coalesce((SELECT array_agg(r.code ORDER BY r.code)
                     FROM variety_region vr JOIN region r ON r.id = vr.region_id
                     WHERE vr.variety_id = v.id), '{}') AS region_codes
    FROM form f
    JOIN variety v ON v.id = f.variety_id
    JOIN concept c ON c.id = f.concept_id AND c.slug IS NOT NULL
    LEFT JOIN source src ON src.id = f.source_id
    WHERE (v.code = :language OR v.code LIKE :language || '-%')
      AND f.status = 'approved' AND f.is_primary
      AND (src.name IS NULL OR NOT (src.name = ANY(:unverified_sources)))
    -- the deck's own variety first (a Hutsul deck gets Hutsul words when there are any)
    ORDER BY v.code = :prefer DESC, random()
    LIMIT :limit
""")

# What a card says the word means: a concept's names and its main Ukrainian / English words
MEANING = text("""
    SELECT c.slug, c.gloss_en, c.gloss_uk, c.glosses,
           (SELECT s.spelling FROM form s JOIN variety u ON u.id = s.variety_id
            WHERE s.concept_id = c.id AND u.code = 'ukr' AND s.is_primary
              AND s.status IN ('approved', 'pending') LIMIT 1) AS standard,
           (SELECT s.spelling FROM form s JOIN variety u ON u.id = s.variety_id
            WHERE s.concept_id = c.id AND u.code = 'eng' AND s.is_primary
              AND s.status IN ('approved', 'pending') LIMIT 1) AS english
    FROM concept c WHERE c.id = :concept_id
""")

# Another concept for a trap: any concept with a page and a Ukrainian name
OTHER_CONCEPT = text("""
    SELECT id FROM concept
    WHERE slug IS NOT NULL AND gloss_uk IS NOT NULL AND id <> :concept_id
    ORDER BY random() LIMIT 1
""")


def sign(nonce: str, language: str, expected: int) -> str:
    message = f"{nonce}|{language}|{expected}".encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()[:24]


def make_token(language: str, expected: int) -> str:
    nonce = secrets.token_urlsafe(12)
    return f"{nonce}.{language}.{sign(nonce, language, expected)}"


def read_token(token: str) -> tuple[str, str, int] | None:
    """(nonce, language, expected answer) of a genuine token, else None."""
    try:
        nonce, language, signature = token.split(".")
    except ValueError:
        return None
    for expected in (1, -1):
        if hmac.compare_digest(signature, sign(nonce, language, expected)):
            return nonce, language, expected
    return None


def gold_cards(
    session: Session, language: str, count: int, prefer: str | None = None
) -> list[GoldCard]:
    """`count` control cards of a language (the `prefer` variety's words first); about a
    third show the word's own meaning."""
    words = list(
        session.execute(
            CHECKED_WORDS,
            {
                "language": language,
                "prefer": prefer or language,
                "unverified_sources": list(UNVERIFIED_SOURCES),
                "limit": count,
            },
        ).mappings()
    )
    cards = []
    for i, word in enumerate(words):
        truthful = i % 3 == 0 and random.random() < 0.9  # noqa: S311 (not security)
        concept_id = word["concept_id"]
        if not truthful:
            other = session.scalar(OTHER_CONCEPT, {"concept_id": concept_id})
            if other is None:
                continue
            concept_id = other
        meaning = session.execute(MEANING, {"concept_id": concept_id}).mappings().one()
        cards.append(
            GoldCard(
                form_id=-random.randint(1, 2**31),  # noqa: S311 (not security)
                spelling=word["spelling"],
                variety_code=word["variety_code"],
                kind=word["kind"],
                variety_name_en=word["variety_name_en"],
                variety_name_uk=word["variety_name_uk"],
                variety_names=word["variety_names"],
                region_codes=word["region_codes"],
                **meaning,
                gold=make_token(language, 1 if truthful else -1),
            )
        )
    random.shuffle(cards)
    return cards


def quiz_status(session: Session, voter: str, language: str) -> QuizStatus:
    """Passed while at least PASS_CORRECT of the voter's last QUIZ_CARDS answers in the
    language are right; after a failure, a new quiz only RETRY_AFTER later."""
    last = list(
        session.execute(
            select(GoldAnswer.correct, GoldAnswer.created_at)
            .where(GoldAnswer.voter == voter, GoldAnswer.language == language)
            .order_by(GoldAnswer.created_at.desc())
            .limit(QUIZ_CARDS)
        )
    )
    if sum(correct for correct, _ in last) >= PASS_CORRECT:
        return QuizStatus(passed=True)
    if len(last) < QUIZ_CARDS:
        return QuizStatus(passed=False)
    wait = last[0][1] + RETRY_AFTER - datetime.now(UTC)
    return QuizStatus(passed=False, retry_after=max(0, int(wait.total_seconds())) or None)


def voter_hash(voter: str) -> str:
    return hashlib.sha256(voter.encode()).hexdigest()


@router.get("/quiz")
def quiz(
    session: SessionDep,
    voter: Annotated[str, Query(min_length=8, max_length=64)],
    language: Annotated[str, Query(pattern=LANGUAGE)],
) -> QuizOut:
    """The quiz before a guest's votes on a language count: QUIZ_CARDS control cards."""
    state = quiz_status(session, voter_hash(voter), language)
    if state.retry_after:
        return QuizOut(cards=[], retry_after=state.retry_after)
    return QuizOut(cards=gold_cards(session, language, QUIZ_CARDS))


@router.get("/quiz/status")
def get_quiz_status(
    session: SessionDep,
    voter: Annotated[str, Query(min_length=8, max_length=64)],
    language: Annotated[str, Query(pattern=LANGUAGE)],
) -> QuizStatus:
    return quiz_status(session, voter_hash(voter), language)


@router.post("/gold")
def answer_gold(session: SessionDep, data: GoldIn) -> GoldResult:
    """An answer to a control card (from the quiz or the game)."""
    parsed = read_token(data.token)
    if parsed is None or parsed[0] in _used_nonces:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or used card")
    nonce, language, expected = parsed
    _used_nonces[nonce] = None
    while len(_used_nonces) > USED_NONCES_KEPT:
        _used_nonces.popitem(last=False)
    voter = voter_hash(data.voter)
    correct = None
    if data.value != 0:
        correct = data.value == expected
        session.add(GoldAnswer(voter=voter, language=language, correct=correct))
        session.commit()
    return GoldResult(correct=correct, passed=quiz_status(session, voter, language).passed)
