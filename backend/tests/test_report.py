"""The weekly report: it is built from the database and goes to the project mailbox."""

import pytest

from app import mail, report
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)


def test_report_has_every_section() -> None:
    subject, body = report.build(7)
    assert subject.startswith("Dialectio: звіт за тиждень")
    for section in ("ТРАФІК", "ШУКАЛИ Й НЕ ЗНАЙШЛИ", "СПІЛЬНОТА", "СЕРВЕР"):
        assert section in body


def test_report_is_emailed(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = []
    monkeypatch.setattr(mail, "deliver", lambda *args: sent.append(args) or True)
    monkeypatch.setattr("sys.argv", ["report"])
    report.main()
    to, subject, body, html, tag = sent[0]
    assert to == "dialectio.team@gmail.com" and tag == "report" and html is None
