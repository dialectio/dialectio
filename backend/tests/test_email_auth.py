"""Emailed links: confirming the address, a new password, signing in without one."""

import uuid
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app import mail
from app.api import accounts, email_auth
from app.db.session import SessionLocal
from app.main import app
from app.models import EmailToken, User
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)


@pytest.fixture
def client() -> Iterator[TestClient]:
    accounts._attempts.clear()
    with TestClient(app) as browser:
        yield browser
    with SessionLocal() as session:
        session.execute(delete(EmailToken).where(EmailToken.email.like("test-%@example.org")))
        session.execute(delete(User).where(User.email.like("test-%@example.org")))
        session.commit()


def email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.org"


def token(sent: list[tuple[str, str, str]], purpose: str) -> str:
    link = next(link for _, p, link in reversed(sent) if p == purpose)
    return parse_qs(urlparse(link).query)["token"][0]


def register(client: TestClient, address: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": address, "password": "secret123", "name": "Ira", "locale": "de"},
    )
    assert response.status_code == 201
    return response.json()


def test_registration_sends_a_confirmation(client: TestClient, no_real_emails: list) -> None:
    address = email()
    assert register(client, address)["email_verified"] is False
    to, purpose, link = no_real_emails[-1]
    assert (to, purpose) == (address, "verify") and link.startswith("http://localhost:3000/de/")

    confirmed = client.post(
        "/api/auth/email/verify", json={"token": token(no_real_emails, "verify")}
    )
    assert confirmed.json()["email_verified"] is True
    # A link works once
    again = client.post("/api/auth/email/verify", json={"token": token(no_real_emails, "verify")})
    assert again.status_code == 400


def test_new_password(client: TestClient, no_real_emails: list) -> None:
    address = email()
    register(client, address)
    with TestClient(app) as other:
        assert other.post("/api/auth/password/forgot", json={"email": address}).status_code == 204
        short = {"token": token(no_real_emails, "reset"), "password": "short"}
        assert other.post("/api/auth/password/reset", json=short).status_code == 422
        done = other.post(
            "/api/auth/password/reset",
            json={"token": token(no_real_emails, "reset"), "password": "new-secret"},
        )
        assert done.status_code == 200 and other.get("/api/auth/me").json()["email"] == address
    # The other browser's old session ended (the email was never proven before)
    assert client.get("/api/auth/me").json() is None
    login = client.post("/api/auth/login", json={"email": address, "password": "new-secret"})
    assert login.status_code == 200


def test_unknown_emails_get_the_same_answer(client: TestClient, no_real_emails: list) -> None:
    response = client.post("/api/auth/password/forgot", json={"email": email()})
    assert response.status_code == 204 and no_real_emails == []


def test_sign_in_link_creates_the_account(client: TestClient, no_real_emails: list) -> None:
    address = email()
    sent = client.post("/api/auth/email/login-link", json={"email": address, "locale": "fr"})
    assert sent.status_code == 204
    me = client.post("/api/auth/email/login", json={"token": token(no_real_emails, "login")})
    assert me.json()["email"] == address and me.json()["email_verified"] is True
    assert client.get("/api/auth/me").json()["name"] == address.split("@")[0]


def test_at_most_three_emails_an_hour(client: TestClient, no_real_emails: list) -> None:
    address = email()
    for _ in range(5):
        client.post("/api/auth/email/login-link", json={"email": address})
    assert len(no_real_emails) == 3


def test_emails_are_rendered_in_every_language() -> None:
    for purpose, texts in mail.TEXTS.items():
        assert set(texts) == set(email_auth.LOCALE.strip("^()$").split("|"))
        for locale in texts:
            subject, text, body = mail.render(purpose, locale, "https://dialectio.org/x?token=a&b")
            assert subject and "https://dialectio.org/x?token=a&b" in text
            assert "token=a&amp;b" in body
