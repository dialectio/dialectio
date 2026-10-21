"""Turnstile: sign-up needs a genuine "I'm human" token once a secret is set."""

import uuid

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app import turnstile
from app.api import accounts
from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models import User
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)


def sign_up(captcha: str) -> int:
    accounts._attempts.clear()
    with TestClient(app) as browser:
        response = browser.post(
            "/api/auth/register",
            json={
                "email": f"test-{uuid.uuid4().hex[:10]}@example.org",
                "password": "secret123",
                "name": "Bot?",
                "captcha": captcha,
            },
        )
    with SessionLocal() as session:
        session.execute(delete(User).where(User.email.like("test-%@example.org")))
        session.commit()
    return response.status_code


def test_sign_up_needs_a_genuine_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "turnstile_secret", "secret")
    checked: list[dict] = []

    def cloudflare(url: str, data: dict, timeout: int) -> httpx2.Response:
        checked.append(data)
        request = httpx2.Request("POST", url)
        return httpx2.Response(200, json={"success": data["response"] == "good"}, request=request)

    monkeypatch.setattr(turnstile.httpx2, "post", cloudflare)
    assert sign_up("") == 400
    assert sign_up("forged") == 400
    assert sign_up("good") == 201
    assert [c["response"] for c in checked] == ["forged", "good"]
