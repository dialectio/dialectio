"""Speaker tests and the languages and dialects members say they speak.

A member who passes the test of a language (SPEAKER_TEST_CARDS control cards, at least
SPEAKER_TEST_PASS right) is a speaker of it: their votes on its words and its dialects' words
count SPEAKER_WEIGHT. Dialects get their own test once they have enough checked words.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SPEAKER_WEIGHT = 1.0


class MemberVariety(Base):
    """A language or dialect a member speaks: said in the profile (a hint), or tested."""

    __tablename__ = "member_variety"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    variety_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    # When the member passed the variety's test; empty while it is only their word
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpeakerTest(Base):
    """One attempt at a speaker test: the cards' answers are counted as they come in."""

    __tablename__ = "speaker_test"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    variety_code: Mapped[str] = mapped_column(String(40))
    cards: Mapped[int] = mapped_column(Integer)
    # Bit i is set once card i is answered
    answered: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    correct: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    passed: Mapped[bool | None] = mapped_column(Boolean)  # None until all cards are answered
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
