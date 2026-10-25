"""Shared test setup."""

from collections.abc import Iterator

import pytest

from app import mail
from app.config import settings


@pytest.fixture(autouse=True, scope="session")
def no_outside_services() -> Iterator[None]:
    """For the whole run, before any fixture of any scope: no email through Brevo (.env may
    hold a real key) and no Turnstile check."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "brevo_api_key", "")
        patch.setattr(settings, "mail_to_log", True)
        patch.setattr(settings, "turnstile_secret", "")
        yield


@pytest.fixture(autouse=True)
def no_real_emails(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[str, str, str]]]:
    """The emails a test caused, collected as (to, purpose, link) instead of being sent."""
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        mail, "send", lambda to, purpose, locale, link: sent.append((to, purpose, link))
    )
    yield sent
