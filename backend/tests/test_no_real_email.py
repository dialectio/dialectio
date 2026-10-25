"""Tests must never reach Brevo, whatever the fixture scope (module-scoped sign-ups once did)."""

import httpx2
import pytest

from app import mail
from app.config import settings


@pytest.fixture(autouse=True, scope="module")
def module_level_sign_up() -> None:
    """Runs where a module-scoped sign-up would: email must already be off here."""
    assert not settings.brevo_api_key and settings.mail_to_log


def test_brevo_is_never_called(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test tried to send a real email")

    monkeypatch.setattr(httpx2, "post", refuse)
    assert mail.deliver("test-y@example.org", "s", "t", None, "verify")
