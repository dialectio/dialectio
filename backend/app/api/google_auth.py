"""Sign in with Google (OpenID Connect, authorization code flow).

/start sends the browser to Google with a random state kept in a short cookie; Google sends it
back to /callback with a code, which the API exchanges for the member's verified email and name.
The member is found by email or created, signed in like after a password login, and sent back
to the page they came from.

An account with a password whose email was never proven loses that password when the owner of
the email signs in with Google, and its other sessions end: someone may have registered another
person's address before them.
"""

import base64
import json
import secrets
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx2
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.accounts import SessionDep, start_session
from app.api.email_links import prove_email
from app.config import settings
from app.models import User

router = APIRouter(prefix="/api/auth/google", tags=["accounts"])

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
STATE_COOKIE = "dialectio_google"
STATE_SECONDS = 600
LOCALES = {"uk", "en", "pl", "de", "es", "fr"}


def redirect_uri() -> str:
    return f"{settings.api_url}/api/auth/google/callback"


def site_page(locale: str, path: str) -> str:
    """A page of the site; only its own paths, so the flow cannot redirect elsewhere."""
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        path = "/"
    return f"{settings.site_url}/{locale}{'' if path == '/' else path}"


def failed(locale: str, path: str, reason: str) -> RedirectResponse:
    query = urlencode({"next": path, "error": reason})
    response = RedirectResponse(f"{site_page(locale, '/login')}?{query}", status_code=303)
    response.delete_cookie(STATE_COOKIE, path="/api/auth/google")
    return response


def exchange_code(code: str) -> dict:
    """The claims of Google's ID token for this code.

    The token comes straight from Google's token endpoint over TLS, so its signature need not
    be checked (OpenID Connect Core 3.1.3.7); audience, issuer and expiry still are.
    """
    response = httpx2.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()["id_token"].split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


@router.get("/start")
def start(locale: str = "uk", next: str = "/") -> RedirectResponse:
    locale = locale if locale in LOCALES else "uk"
    if not settings.google_client_id:
        return failed(locale, next, "google_off")
    state = secrets.token_urlsafe(24)
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )
    response = RedirectResponse(f"{AUTHORIZE_URL}?{query}", status_code=303)
    response.set_cookie(
        STATE_COOKIE,
        json.dumps({"state": state, "locale": locale, "next": next}),
        max_age=STATE_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",  # sent on Google's top-level redirect back
        path="/api/auth/google",
    )
    return response


@router.get("/callback")
def callback(
    request: Request,
    session: SessionDep,
    state: str = "",
    code: str = "",
    error: str = "",
) -> RedirectResponse:
    try:
        saved = json.loads(request.cookies.get(STATE_COOKIE, ""))
        locale, path = saved["locale"], saved["next"]
    except (ValueError, KeyError, TypeError):
        return failed("uk", "/", "google")
    if error or not code or not secrets.compare_digest(state, str(saved.get("state", ""))):
        return failed(locale, path, "google")
    try:
        claims = exchange_code(code)
    except (httpx2.HTTPError, KeyError, IndexError, ValueError):
        return failed(locale, path, "google")
    email = str(claims.get("email", "")).strip().lower()
    if (
        claims.get("aud") != settings.google_client_id
        or claims.get("iss") not in ISSUERS
        or float(claims.get("exp", 0)) < datetime.now(UTC).timestamp()
        or not email
        or claims.get("email_verified") is not True
    ):
        return failed(locale, path, "google")

    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        name = str(claims.get("given_name") or claims.get("name") or email.split("@")[0])
        user = User(email=email, name=name.strip()[:60] or "?")
        session.add(user)
        session.flush()
    prove_email(session, user)

    response = RedirectResponse(site_page(locale, path), status_code=303)
    response.delete_cookie(STATE_COOKIE, path="/api/auth/google")
    start_session(session, response, user)
    return response
