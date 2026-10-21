"""Trust beyond the speaker test: experts of a language or dialect, and the change log.

Experts are speakers an editor approved for one variety (a language covers its dialects):
they review submitted words and drafts of it, fix spellings and close mistake reports, and
their votes count EXPERT_WEIGHT. Every change editors and experts make to a word is logged.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

TRUSTED_WEIGHT = 2.0  # a speaker whose control answers are reliably right
EXPERT_WEIGHT = 3.0

APPLIED = "applied"
EXPERT = "expert"
DECLINED = "declined"


class ExpertRole(Base):
    """A member's application to be an expert of a variety, and the editor's decision."""

    __tablename__ = "expert_role"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    variety_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(10), default=APPLIED, server_default=APPLIED)
    # Who they are: "I teach dialectology at ...", "born and live in Verkhovyna"
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FormChange(Base):
    """One change to a word by an editor or an expert, with what it was and what it became."""

    __tablename__ = "form_change"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int | None] = mapped_column(
        ForeignKey("form.id", ondelete="SET NULL"), index=True
    )
    concept_id: Mapped[int | None] = mapped_column(Integer)
    variety_code: Mapped[str] = mapped_column(String(40), index=True)
    spelling: Mapped[str] = mapped_column(String(200))  # the word when it was changed
    action: Mapped[str] = mapped_column(String(10))  # add, approve, reject, spelling, ...
    before: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    after: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    # An expert (their account, and their name then); None = the editors
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    actor: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
