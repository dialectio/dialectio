"""Accounts: members who sign in (email and password or Google; email links later)
and their sessions. Guests keep using the site without an account."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MEMBER = "member"
EDITOR = "editor"


class User(Base):
    __tablename__ = "app_user"  # "user" is a reserved word in PostgreSQL

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored in lower case
    # Shown under the words and recordings the member adds
    name: Mapped[str] = mapped_column(String(60))
    # scrypt hash (app/api/accounts.py); empty for accounts that only sign in with Google
    password_hash: Mapped[str | None] = mapped_column(String(200))
    # When the member proved they own the email (Google sign-in; email links later)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(String(20), default=MEMBER, server_default=MEMBER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base):
    """A signed-in browser: the cookie holds a random token, only its hash is stored."""

    __tablename__ = "auth_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EmailToken(Base):
    """A one-time link sent by email: confirm the address, set a new password, or sign in.
    Only the token's hash is stored."""

    __tablename__ = "email_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(10))  # verify, reset, login
    email: Mapped[str] = mapped_column(String(254), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
