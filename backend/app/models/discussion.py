"""Discussions: members' comments on a word (a form, i.e. the word in one language or dialect).

Comments show at once. Anyone can report one (the EU Digital Services Act asks for a way to
flag illegal content); after HIDE_AFTER reports from different members it is hidden until an
editor decides. Editors, and experts of the word's variety, hide comments; authors edit and
delete their own. Deleting an account deletes its comments.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

VISIBLE = "visible"
HIDDEN = "hidden"  # by an editor or an expert, or after HIDE_AFTER members' reports

HIDE_AFTER = 3
MAX_COMMENT = 2000


class Comment(Base):
    __tablename__ = "comment"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("form.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    # The comment it answers (shown as a quote); the answer stays if that one is deleted
    reply_to_id: Mapped[int | None] = mapped_column(ForeignKey("comment.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default=VISIBLE, server_default=VISIBLE)
    # Who hid it: "editor", "expert:<user id>" or "reports"
    hidden_by: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommentReport(Base):
    """A report of a comment: by a member ("user:<id>") or a guest (their browser's id),
    stored as a hash like votes."""

    __tablename__ = "comment_report"
    __table_args__ = (UniqueConstraint("comment_id", "reporter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comment.id", ondelete="CASCADE"), index=True
    )
    reporter: Mapped[str] = mapped_column(String(64))
    # Members' reports hide a comment after HIDE_AFTER; guests' only reach the editors
    member: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
