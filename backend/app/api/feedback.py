"""Visitors check words: "do people say it like this?" votes and "mistake?" reports.

No accounts: the browser sends a random voter id, stored only as a SHA-256 hash, so a
browser has one vote per word (and can change it). Spam protection: per-IP limits kept in
memory only, and a honeypot field on reports. Votes never change a word; they add a
"confirmed by speakers" or "disputed" mark, and editors see them in the editor.
"""

import hashlib
import re
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.api.lexicon import UNVERIFIED_SOURCES, SessionDep
from app.models import (
    PUBLIC_STATUSES,
    Form,
    MissingSearch,
    Region,
    Report,
    Vote,
    community_status,
)

router = APIRouter(prefix="/api", tags=["feedback"])

VOTE_LIMIT = (300, 24 * 3600)  # votes per IP per day
REPORT_LIMIT = (20, 3600)  # reports per IP per hour

_recent: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def check_limit(kind: str, request: Request, limit: tuple[int, int]) -> None:
    count, seconds = limit
    ip = request.client.host if request.client else "unknown"
    window = _recent[(kind, ip)]
    now = time.monotonic()
    while window and now - window[0] > seconds:
        window.popleft()
    if len(window) >= count:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")
    window.append(now)


def voter_hash(voter: str) -> str:
    return hashlib.sha256(voter.encode()).hexdigest()


class VoteIn(BaseModel):
    form_id: int
    # 1 = "yes", -1 = "no", 0 = take the vote back
    value: int = Field(ge=-1, le=1)
    voter: str = Field(min_length=8, max_length=64)
    region_code: str | None = Field(default=None, max_length=10)


class VoteCounts(BaseModel):
    form_id: int
    yes: int
    no: int
    community: str | None


class ReportIn(BaseModel):
    form_id: int
    message: str = Field(min_length=1, max_length=1000)
    voter: str | None = Field(default=None, max_length=64)
    region_code: str | None = Field(default=None, max_length=10)
    # Honeypot: hidden in the form, only bots fill it in
    website: str = ""

    @field_validator("message")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


def public_form(session: SessionDep, form_id: int) -> Form:
    form = session.get(Form, form_id)
    if form is None or form.status not in PUBLIC_STATUSES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Word not found")
    return form


def known_region(session: SessionDep, code: str | None) -> str | None:
    if not code:
        return None
    return code if session.scalar(select(Region.id).where(Region.code == code)) else None


def counts(session: SessionDep, form_id: int) -> VoteCounts:
    yes, no = session.execute(
        select(
            func.count().filter(Vote.value > 0),
            func.count().filter(Vote.value < 0),
        ).where(Vote.form_id == form_id)
    ).one()
    return VoteCounts(form_id=form_id, yes=yes, no=no, community=community_status(yes, no))


@router.post("/votes")
def vote(session: SessionDep, request: Request, data: VoteIn) -> VoteCounts:
    check_limit("vote", request, VOTE_LIMIT)
    public_form(session, data.form_id)
    voter = voter_hash(data.voter)
    if data.value == 0:
        session.execute(
            Vote.__table__.delete().where(Vote.form_id == data.form_id, Vote.voter == voter)
        )
    else:
        statement = insert(Vote).values(
            form_id=data.form_id,
            value=data.value,
            voter=voter,
            region_code=known_region(session, data.region_code),
        )
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Vote.form_id, Vote.voter],
                set_={
                    "value": statement.excluded.value,
                    "region_code": statement.excluded.region_code,
                },
            )
        )
    session.commit()
    return counts(session, data.form_id)


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def report(session: SessionDep, request: Request, data: ReportIn) -> dict[str, str]:
    if data.website:  # a bot filled the hidden field; pretend it worked
        return {"status": "ok"}
    if not data.message:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Message is empty")
    check_limit("report", request, REPORT_LIMIT)
    public_form(session, data.form_id)
    session.add(
        Report(
            form_id=data.form_id,
            message=data.message,
            voter=voter_hash(data.voter) if data.voter else None,
            region_code=known_region(session, data.region_code),
        )
    )
    session.commit()
    return {"status": "ok"}


class RegionOption(BaseModel):
    code: str
    name_en: str
    name_uk: str | None
    names: dict[str, str] = {}
    # False for regions abroad where Ukrainian dialects are spoken (Lemko, Hutsul areas...)
    in_ukraine: bool


VOTER_REGIONS = text("""
    SELECT r.code, r.name_en, r.name_uk, r.names, r.code LIKE 'UA-%' AS in_ukraine
    FROM region r
    WHERE r.level = 'adm1'
      AND (r.code LIKE 'UA-%' OR r.id IN (
          SELECT vr.region_id FROM variety_region vr
          JOIN variety v ON v.id = vr.variety_id AND v.kind = 'dialect'))
    ORDER BY in_ukraine DESC, coalesce(r.name_uk, r.name_en)
""")


@router.get("/regions/voter")
def voter_regions(session: SessionDep) -> list[RegionOption]:
    """Answers to "where do you live?": Ukraine's oblasts, then the regions abroad where
    Ukrainian dialects are spoken."""
    return [RegionOption(**row) for row in session.execute(VOTER_REGIONS).mappings()]


# --- "Check words" game: cards of unverified words to vote on -----------------------------

# The deck for Ukrainian: standard Ukrainian and all its dialects.
UKRAINIAN_DECK = "ukr"
CARDS_MAX = 30

UNVERIFIED_FORMS = """
    FROM form f
    JOIN variety v ON v.id = f.variety_id
    LEFT JOIN source src ON src.id = f.source_id
    WHERE f.status IN ('approved', 'pending')
      AND (f.status = 'pending' OR src.name = ANY(:unverified_sources))
"""

DECKS = text(f"""
    SELECT CASE WHEN v.code LIKE 'ukr-%' THEN 'ukr' ELSE v.code END AS code,
           count(*) AS words
    {UNVERIFIED_FORMS}
    GROUP BY 1
    ORDER BY 2 DESC
""")

CARDS = text("""
    SELECT f.id AS form_id, f.spelling, v.code AS variety_code, v.kind,
           v.name_en AS variety_name_en, v.name_uk AS variety_name_uk,
           v.names AS variety_names, c.slug, c.gloss_en, c.gloss_uk, c.glosses,
           (SELECT s.spelling FROM form s JOIN variety u ON u.id = s.variety_id
            WHERE s.concept_id = c.id AND u.code = 'ukr' AND s.is_primary
              AND s.status IN ('approved', 'pending') LIMIT 1) AS standard,
           (SELECT s.spelling FROM form s JOIN variety u ON u.id = s.variety_id
            WHERE s.concept_id = c.id AND u.code = 'eng' AND s.is_primary
              AND s.status IN ('approved', 'pending') LIMIT 1) AS english,
           coalesce((SELECT array_agg(r.code ORDER BY r.code)
                     FROM variety_region vr JOIN region r ON r.id = vr.region_id
                     WHERE vr.variety_id = v.id), '{}') AS region_codes,
           (SELECT count(*) FROM vote x WHERE x.form_id = f.id) AS votes
    FROM form f
    JOIN variety v ON v.id = f.variety_id
    JOIN concept c ON c.id = f.concept_id AND c.slug IS NOT NULL
    LEFT JOIN source src ON src.id = f.source_id
    WHERE f.status IN ('approved', 'pending')
      AND (f.status = 'pending' OR src.name = ANY(:unverified_sources))
      AND (CASE WHEN :deck = 'ukr' THEN v.code = 'ukr' OR v.code LIKE 'ukr-%'
                ELSE v.code = :deck END)
      AND NOT EXISTS (SELECT 1 FROM vote x WHERE x.form_id = f.id AND x.voter = :voter)
      AND NOT (f.id = ANY(:skip))
    ORDER BY votes, random()
    LIMIT :limit
""")


class Deck(BaseModel):
    code: str  # "ukr" (Ukrainian with its dialects) or a language code
    name_en: str
    name_uk: str | None
    names: dict[str, str] = {}
    words: int  # unverified words to check


class Card(BaseModel):
    form_id: int
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
    standard: str | None  # the standard Ukrainian word for the concept
    english: str | None
    region_codes: list[str]
    votes: int


@router.get("/check/decks")
def check_decks(session: SessionDep) -> list[Deck]:
    """Word sets to check: Ukrainian with its dialects, and every language with unverified words."""
    names = {
        code: (en, uk, local)
        for code, en, uk, local in session.execute(
            text("SELECT code, name_en, name_uk, names FROM variety")
        )
    }
    return [
        Deck(
            code=code,
            name_en=names[code][0],
            name_uk=names[code][1],
            names=names[code][2],
            words=words,
        )
        for code, words in session.execute(DECKS, {"unverified_sources": list(UNVERIFIED_SOURCES)})
        if code in names
    ]


@router.get("/check/cards")
def check_cards(
    session: SessionDep,
    voter: Annotated[str, Query(min_length=8, max_length=64)],
    deck: str = UKRAINIAN_DECK,
    skip: Annotated[list[int], Query()] = [],  # noqa: B006 (FastAPI copies defaults)
    limit: Annotated[int, Query(ge=1, le=CARDS_MAX)] = 10,
) -> list[Card]:
    """Unverified words this browser has not voted on yet, least-voted first."""
    rows = session.execute(
        CARDS,
        {
            "unverified_sources": list(UNVERIFIED_SOURCES),
            "deck": deck,
            "voter": voter_hash(voter),
            "skip": skip,
            "limit": limit,
        },
    ).mappings()
    return [Card(**row) for row in rows]


# --- Searches that found nothing: the dictionary's to-do list ----------------------------

MISSING_LIMIT = (60, 3600)  # recorded searches per IP per hour
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


class MissingIn(BaseModel):
    q: str = Field(min_length=2, max_length=50)


@router.post("/missing", status_code=status.HTTP_204_NO_CONTENT)
def record_missing(session: SessionDep, request: Request, data: MissingIn) -> None:
    """The visitor searched for this and found nothing (sent once they stop typing)."""
    query = " ".join(data.q.lower().split())
    if len(query) < 2 or not LETTER.search(query):
        return
    check_limit("missing", request, MISSING_LIMIT)
    statement = insert(MissingSearch).values(query=query)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[MissingSearch.query],
            set_={"count": MissingSearch.count + 1, "last_seen": func.now()},
        )
    )
    session.commit()
