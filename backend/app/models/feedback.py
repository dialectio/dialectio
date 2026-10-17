"""Visitors' feedback on words: "do people say it like this?" votes and error reports.

Visitors have no accounts: a vote is tied to a random id their browser keeps (stored only
as a hash), so one browser has one vote per word and can change it.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Vote(Base):
    __tablename__ = "vote"
    __table_args__ = (UniqueConstraint("form_id", "voter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("form.id", ondelete="CASCADE"), index=True)
    # +1: "yes, people say it like this", -1: "no"
    value: Mapped[int] = mapped_column(SmallInteger)
    # Where the voter says they live (region code such as "UA-26"), optional
    region_code: Mapped[str | None] = mapped_column(String(10))
    # SHA-256 of the browser's random voter id
    voter: Mapped[str] = mapped_column(String(64))
    # How much the vote counts, set when it is cast: a guest who passed the quiz of the word's
    # language counts GUEST_WEIGHT, one who didn't counts nothing (the vote is still kept)
    weight: Mapped[float] = mapped_column(Float, default=0.25, server_default="0.25")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GoldAnswer(Base):
    """An answer to a control card (a word with a known answer) in the quiz or the game: how
    a voter's answers are checked without accounts."""

    __tablename__ = "gold_answer"

    id: Mapped[int] = mapped_column(primary_key=True)
    voter: Mapped[str] = mapped_column(String(64), index=True)
    # The language the card tested ("ukr" for Ukrainian and its dialects, "deu", "cym" ...)
    language: Mapped[str] = mapped_column(String(10))
    correct: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("form.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(Text)
    region_code: Mapped[str | None] = mapped_column(String(10))
    voter: Mapped[str | None] = mapped_column(String(64))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Votes are weighted (a guest who passed the quiz: GUEST_WEIGHT; speakers more, later). A word
# counts as confirmed by speakers with at least CONFIRM_MIN of "yes" weight making up
# CONFIRM_SHARE of all its weight; as disputed with at least DISPUTE_MIN of "no" weight not
# outnumbered by "yes" weight. Editors' ✓ stays separate and above both.
GUEST_WEIGHT = 0.25
MEMBER_WEIGHT = 0.5  # a signed-in member who passed the quiz
CONFIRM_MIN = 5
CONFIRM_SHARE = 0.8
DISPUTE_MIN = 3
CONFIRMED = "confirmed"
DISPUTED = "disputed"


def community_status(yes: float, no: float) -> str | None:
    """The mark from the weight of "yes" and "no" votes."""
    if yes >= CONFIRM_MIN and yes >= CONFIRM_SHARE * (yes + no):
        return CONFIRMED
    if no >= DISPUTE_MIN and no >= yes:
        return DISPUTED
    return None


class MissingSearch(Base):
    """A search that found nothing: what the dictionary should add next. Only the query
    text and a counter are kept, nothing about who searched."""

    __tablename__ = "missing_search"

    query: Mapped[str] = mapped_column(String(100), primary_key=True)
    count: Mapped[int] = mapped_column(default=1, server_default="1")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
