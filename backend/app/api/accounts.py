"""Accounts: sign up and sign in with an email and a password, sign out, delete the account.

The session is an HttpOnly cookie with a random token; the database keeps only its hash.
Passwords are hashed with scrypt (Python's standard library). A signed-in member votes and
answers control cards as themselves, from any browser: their voter id is "user:<id>"
instead of the browser's random id.
"""

import base64
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_session
from app.models import AuthSession, User

router = APIRouter(prefix="/api/auth", tags=["accounts"])

COOKIE = "dialectio_session"
SESSION_DAYS = 30
MIN_PASSWORD = 8
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# scrypt parameters: ~50 ms per hash, 16 MB of memory
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1

LOGIN_LIMIT = (20, 15 * 60)  # attempts per IP per 15 minutes
REGISTER_LIMIT = (10, 3600)  # accounts per IP per hour
_attempts: dict[tuple[str, str], deque[float]] = defaultdict(deque)

SessionDep = Annotated[Session, Depends(get_session)]


def check_limit(kind: str, request: Request, limit: tuple[int, int]) -> None:
    count, seconds = limit
    ip = request.client.host if request.client else "unknown"
    window = _attempts[(kind, ip)]
    now = time.monotonic()
    while window and now - window[0] > seconds:
        window.popleft()
    if len(window) >= count:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts")
    window.append(now)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    encode = base64.b64encode
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encode(salt).decode()}${encode(key).decode()}"


def check_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, n, r, p, salt, key = stored.split("$")
        expected = base64.b64decode(key)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p)
        )
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(session: Session, response: Response, user: User) -> None:
    token = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=datetime.now(UTC) + timedelta(days=SESSION_DAYS),
        )
    )
    session.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def current_user(request: Request, session: Session) -> User | None:
    """The signed-in member, if the request has a valid session cookie."""
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    found = session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(token),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    return session.get(User, found.user_id) if found else None


def voter_of(request: Request, session: Session, browser_voter: str) -> str:
    """The id votes and control answers are kept under: the member's, else the browser's."""
    user = current_user(request, session)
    return f"user:{user.id}" if user else browser_voter


class Me(BaseModel):
    id: int
    email: str
    name: str
    role: str


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().lower()


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=60)
    website: str = ""  # honeypot: hidden in the form, only bots fill it in

    @field_validator("name")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


def me(user: User) -> Me:
    return Me(id=user.id, email=user.email, name=user.name, role=user.role)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: Registration, request: Request, response: Response, session: SessionDep) -> Me:
    check_limit("register", request, REGISTER_LIMIT)
    if data.website:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Rejected")
    if not EMAIL.match(data.email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_email")
    if len(data.password) < MIN_PASSWORD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "short_password")
    if not data.name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_name")
    if session.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email_taken")
    user = User(email=data.email, name=data.name, password_hash=hash_password(data.password))
    session.add(user)
    session.flush()
    start_session(session, response, user)
    return me(user)


@router.post("/login")
def login(data: Credentials, request: Request, response: Response, session: SessionDep) -> Me:
    check_limit("login", request, LOGIN_LIMIT)
    user = session.scalar(select(User).where(User.email == data.email))
    if user is None or not check_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong_credentials")
    start_session(session, response, user)
    return me(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: SessionDep) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        session.commit()
    response.delete_cookie(COOKIE, path="/")


@router.get("/me")
def get_me(request: Request, session: SessionDep) -> Me | None:
    """The signed-in member, or null for a guest."""
    user = current_user(request, session)
    return me(user) if user else None


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(request: Request, response: Response, session: SessionDep) -> None:
    """Delete the account and its sessions. Votes stay, anonymous (no email or name)."""
    user = current_user(request, session)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_signed_in")
    session.delete(user)
    session.commit()
    response.delete_cookie(COOKIE, path="/")
