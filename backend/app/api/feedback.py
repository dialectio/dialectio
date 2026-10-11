"""Visitors check words: "do people say it like this?" votes and "mistake?" reports.

No accounts: the browser sends a random voter id, stored only as a SHA-256 hash, so a
browser has one vote per word (and can change it). Spam protection: per-IP limits kept in
memory only, and a honeypot field on reports. Votes never change a word; they add a
"confirmed by speakers" or "disputed" mark, and editors see them in the editor.
"""

import hashlib
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.lexicon import SessionDep
from app.models import PUBLIC_STATUSES, Form, Region, Report, Vote, community_status

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


@router.get("/regions/ukraine")
def ukraine_regions(session: SessionDep) -> list[RegionOption]:
    """Oblasts for "where do you live?" (sorted by Ukrainian name)."""
    rows = session.scalars(
        select(Region)
        .where(Region.level == "adm1", Region.code.like("UA-%"))
        .order_by(func.coalesce(Region.name_uk, Region.name_en))
    )
    return [RegionOption(code=r.code, name_en=r.name_en, name_uk=r.name_uk) for r in rows]
