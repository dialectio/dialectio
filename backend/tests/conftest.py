"""Shared test setup."""

from collections.abc import Iterator

import pytest

from app import mail
from app.config import settings


@pytest.fixture(autouse=True)
def no_real_emails(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[str, str, str]]]:
    """Tests never send email through Brevo (.env may hold a real key); the emails a test
    caused are collected as (to, purpose, link)."""
    monkeypatch.setattr(settings, "brevo_api_key", "")
    monkeypatch.setattr(settings, "turnstile_secret", "")  # tests aren't asked to be human
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        mail, "send", lambda to, purpose, locale, link: sent.append((to, purpose, link))
    )
    yield sent
