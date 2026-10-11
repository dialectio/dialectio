"""Visitors' feedback on words: "do people say it like this?" votes and error reports.

Visitors have no accounts: a vote is tied to a random id their browser keeps (stored only
as a hash), so one browser has one vote per word and can change it.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
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


# A word counts as confirmed by speakers with at least CONFIRM_MIN "yes" votes that make up
# CONFIRM_SHARE of all its votes; as disputed with at least DISPUTE_MIN "no" votes that are
# not outnumbered by "yes" votes. Editors' ✓ stays separate and above both.
CONFIRM_MIN = 5
CONFIRM_SHARE = 0.8
DISPUTE_MIN = 3
CONFIRMED = "confirmed"
DISPUTED = "disputed"


def community_status(yes: int, no: int) -> str | None:
    if yes >= CONFIRM_MIN and yes >= CONFIRM_SHARE * (yes + no):
        return CONFIRMED
    if no >= DISPUTE_MIN and no >= yes:
        return DISPUTED
    return None
