"""Emailed links: confirm the address, set a new password ("forgot password?"), sign in
without a password. Requests that name an email answer the same whether an account exists
or not, so they don't tell who is registered."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.accounts import (
    EMAIL,
    MIN_PASSWORD,
    Me,
    SessionDep,
    check_limit,
    hash_password,
    me,
    require_member,
    start_session,
)
from app.api.email_links import prove_email, send_link, use_token
from app.models import User
from app.turnstile import require_human

router = APIRouter(prefix="/api/auth", tags=["accounts"])

MAIL_LIMIT = (10, 3600)  # emails asked for per IP per hour
LOCALE = "^(uk|en|pl|de|es|fr)$"


class EmailIn(BaseModel):
    email: str = Field(max_length=254)
    locale: str = Field(default="uk", pattern=LOCALE)
    captcha: str = Field(default="", max_length=2048)  # Turnstile token

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().lower()


class LocaleIn(BaseModel):
    locale: str = Field(default="uk", pattern=LOCALE)


class TokenIn(BaseModel):
    token: str = Field(max_length=100)


class NewPassword(TokenIn):
    password: str = Field(max_length=200)


@router.post("/email/verification", status_code=status.HTTP_204_NO_CONTENT)
def resend_verification(
    data: LocaleIn, request: Request, background: BackgroundTasks, session: SessionDep
) -> None:
    """Send the signed-in member a new link to confirm their email."""
    user = require_member(request, session)
    check_limit("mail", request, MAIL_LIMIT)
    if user.email_verified_at is None:
        send_link(session, background, "verify", user.email, data.locale)


@router.post("/email/verify")
def verify_email(data: TokenIn, session: SessionDep) -> Me:
    email = use_token(session, data.token, "verify")
    user = session.scalar(select(User).where(User.email == email)) if email else None
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_link")
    prove_email(session, user, keep_password=True)  # the link went to whoever registered
    session.commit()
    return me(user)


@router.post("/password/forgot", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(
    data: EmailIn, request: Request, background: BackgroundTasks, session: SessionDep
) -> None:
    check_limit("mail", request, MAIL_LIMIT)
    require_human(request, data.captcha)
    if session.scalar(select(User.id).where(User.email == data.email)):
        send_link(session, background, "reset", data.email, data.locale)


@router.post("/password/reset")
def reset_password(data: NewPassword, response: Response, session: SessionDep) -> Me:
    """A new password from an emailed link; every other session of the account ends."""
    if len(data.password) < MIN_PASSWORD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "short_password")
    email = use_token(session, data.token, "reset")
    user = session.scalar(select(User).where(User.email == email)) if email else None
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_link")
    prove_email(session, user)
    user.password_hash = hash_password(data.password)
    start_session(session, response, user)
    return me(user)


@router.post("/email/login-link", status_code=status.HTTP_204_NO_CONTENT)
def send_login_link(
    data: EmailIn, request: Request, background: BackgroundTasks, session: SessionDep
) -> None:
    """A sign-in link; following it creates the account if there is none yet."""
    check_limit("mail", request, MAIL_LIMIT)
    require_human(request, data.captcha)
    if not EMAIL.match(data.email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_email")
    send_link(session, background, "login", data.email, data.locale)


@router.post("/email/login")
def login_with_link(data: TokenIn, response: Response, session: SessionDep) -> Me:
    email = use_token(session, data.token, "login")
    if email is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_link")
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=email.split("@")[0][:60] or "?")
        session.add(user)
        session.flush()
    prove_email(session, user)
    start_session(session, response, user)
    return me(user)
