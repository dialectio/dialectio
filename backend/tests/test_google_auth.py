"""Sign in with Google: the redirect, the state check, new and existing accounts."""

import time
import uuid
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api import accounts, google_auth
from app.db.session import SessionLocal
from app.main import app
from app.models import User
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)

CLIENT_ID = "test-client.apps.googleusercontent.com"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(google_auth.settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(accounts, "_attempts", accounts.defaultdict(accounts.deque))
    with TestClient(app, follow_redirects=False) as browser:
        yield browser
    with SessionLocal() as session:
        session.execute(delete(User).where(User.email.like("test-%@example.org")))
        session.commit()


def email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.org"


def google_returns(monkeypatch: pytest.MonkeyPatch, address: str, **claims: object) -> None:
    token = {
        "aud": CLIENT_ID,
        "iss": "https://accounts.google.com",
        "exp": time.time() + 600,
        "email": address,
        "email_verified": True,
        "given_name": "Olena",
        **claims,
    }
    monkeypatch.setattr(google_auth, "exchange_code", lambda code: token)


def sign_in(client: TestClient, next: str = "/word/water") -> str:
    """Goes through /start and /callback; returns where the member lands."""
    start = client.get("/api/auth/google/start", params={"locale": "en", "next": next})
    assert start.status_code == 303
    google = parse_qs(urlparse(start.headers["location"]).query)
    assert google["client_id"] == [CLIENT_ID]
    assert google["redirect_uri"] == ["http://localhost:8000/api/auth/google/callback"]
    back = client.get(
        "/api/auth/google/callback", params={"state": google["state"][0], "code": "x"}
    )
    assert back.status_code == 303
    return back.headers["location"]


def test_new_member_signs_in(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    address = email()
    google_returns(monkeypatch, address)
    assert sign_in(client) == "http://localhost:3000/en/word/water"
    me = client.get("/api/auth/me").json()
    assert me["email"] == address and me["name"] == "Olena"


def test_existing_password_account_is_taken_over_safely(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    address = email()
    with TestClient(app) as squatter:
        squatter.post(
            "/api/auth/register",
            json={"email": address, "password": "secret123", "name": "Someone"},
        )
        google_returns(monkeypatch, address)
        sign_in(client)
        # The email's real owner is in; the earlier password and session no longer work
        assert client.get("/api/auth/me").json()["name"] == "Someone"
        assert squatter.get("/api/auth/me").json() is None
        login = squatter.post("/api/auth/login", json={"email": address, "password": "secret123"})
        assert login.status_code == 401
    with SessionLocal() as session:
        assert session.scalar(select(User.email_verified_at).where(User.email == address))


def test_wrong_state_or_unverified_email_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    google_returns(monkeypatch, email())
    client.get("/api/auth/google/start", params={"locale": "de", "next": "/"})
    back = client.get("/api/auth/google/callback", params={"state": "forged", "code": "x"})
    assert back.headers["location"].startswith("http://localhost:3000/de/login?")
    assert "error=google" in back.headers["location"]

    google_returns(monkeypatch, email(), email_verified=False)
    assert "error=google" in sign_in(client)
    assert client.get("/api/auth/me").json() is None


def test_only_own_pages_after_sign_in(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    google_returns(monkeypatch, email())
    assert sign_in(client, next="//evil.example/x") == "http://localhost:3000/en"
