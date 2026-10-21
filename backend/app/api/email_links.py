"""One-time links sent by email, and proving that a member owns their email address.

A link is `<site>/<locale>/auth/<purpose>?token=...`; the page there sends the token back to
the API when the member presses its button (mail scanners that open links don't use it up).
Only the token's hash is stored. At most MAX_PER_HOUR emails go to one address an hour.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import mail
from app.config import settings
from app.models import AuthSession, EmailToken, User

LIFETIMES = {
    "verify": timedelta(days=3),
    "reset": timedelta(hours=1),
    "login": timedelta(minutes=15),
}
MAX_PER_HOUR = 3
LOCALES = {"uk", "en", "pl", "de", "es", "fr"}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def send_link(
    session: Session, background: BackgroundTasks, purpose: str, email: str, locale: str
) -> None:
    """Make a one-time link and email it (quietly nothing if the address got enough already)."""
    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    recent = session.scalar(
        select(func.count()).where(EmailToken.email == email, EmailToken.created_at > hour_ago)
    )
    if recent >= MAX_PER_HOUR:
        return
    token = secrets.token_urlsafe(32)
    session.add(
        EmailToken(
            token_hash=token_hash(token),
            purpose=purpose,
            email=email,
            expires_at=datetime.now(UTC) + LIFETIMES[purpose],
        )
    )
    session.commit()
    locale = locale if locale in LOCALES else "en"
    link = f"{settings.site_url}/{locale}/auth/{purpose}?token={token}"
    background.add_task(mail.send, email, purpose, locale, link)


def use_token(session: Session, token: str, purpose: str) -> str | None:
    """The email a valid, unused link of this purpose was sent to; the link is used up."""
    found = session.scalar(
        select(EmailToken)
        .where(
            EmailToken.token_hash == token_hash(token),
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
            EmailToken.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    if found is None:
        return None
    found.used_at = datetime.now(UTC)
    return found.email


def prove_email(session: Session, user: User, keep_password: bool = False) -> None:
    """The member showed they own the address (Google, an emailed link). If it was never
    proven before, someone else may have registered it with a password: that password and
    every session of the account end."""
    if user.email_verified_at is None and not keep_password:
        user.password_hash = None
        session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)
