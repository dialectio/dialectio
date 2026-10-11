"""Visitors' votes and error reports (need the local database with imported data)."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api import feedback
from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models import Report, Vote, community_status
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)

client = TestClient(app)
TOKEN = "test-token"


@pytest.fixture
def form() -> Iterator[dict]:
    """A public dialect word, with its votes and reports removed after the test."""
    detail = client.get("/api/concepts/by-slug/potato").json()
    word = next(
        f for lang in detail["languages"] if lang["kind"] == "dialect" for f in lang["forms"]
    )
    yield word
    with SessionLocal() as session:
        session.execute(delete(Vote).where(Vote.form_id == word["id"]))
        session.execute(delete(Report).where(Report.form_id == word["id"]))
        session.commit()


@pytest.fixture(autouse=True)
def no_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feedback, "_recent", feedback.defaultdict(feedback.deque))
    monkeypatch.setattr(settings, "editor_token", TOKEN)


def vote(form_id: int, value: int, voter: str | None = None, region: str | None = None) -> dict:
    response = client.post(
        "/api/votes",
        json={
            "form_id": form_id,
            "value": value,
            "voter": voter or uuid.uuid4().hex,
            "region_code": region,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_community_status_rules() -> None:
    assert community_status(4, 0) is None
    assert community_status(5, 1) == "confirmed"
    assert community_status(5, 2) is None  # 71 % "yes" is not enough
    assert community_status(1, 3) == "disputed"
    assert community_status(4, 3) is None


def test_votes_confirm_a_word_and_show_on_its_page(form: dict) -> None:
    for _ in range(5):
        result = vote(form["id"], 1, region="UA-26")
    assert result == {"form_id": form["id"], "yes": 5, "no": 0, "community": "confirmed"}

    detail = client.get("/api/concepts/by-slug/potato").json()
    shown = next(f for lang in detail["languages"] for f in lang["forms"] if f["id"] == form["id"])
    assert shown["votes_yes"] == 5 and shown["community"] == "confirmed"


def test_one_vote_per_browser_can_change_and_be_taken_back(form: dict) -> None:
    voter = uuid.uuid4().hex
    assert vote(form["id"], 1, voter)["yes"] == 1
    assert vote(form["id"], -1, voter) == {
        "form_id": form["id"],
        "yes": 0,
        "no": 1,
        "community": None,
    }
    assert vote(form["id"], 0, voter)["no"] == 0


def test_unknown_region_and_word(form: dict) -> None:
    vote(form["id"], 1, region="XX-99")  # stored without a region, not rejected
    response = client.post("/api/votes", json={"form_id": 0, "value": 1, "voter": uuid.uuid4().hex})
    assert response.status_code == 404


def test_report_reaches_the_editor_and_can_be_resolved(form: dict) -> None:
    headers = {"X-Editor-Token": TOKEN}
    bot = client.post(
        "/api/reports", json={"form_id": form["id"], "message": "spam", "website": "x"}
    )
    assert bot.status_code == 201  # honeypot: accepted silently, not stored

    for _ in range(3):
        vote(form["id"], -1, region="UA-77")
    sent = client.post("/api/reports", json={"form_id": form["id"], "message": "  Так не кажуть  "})
    assert sent.status_code == 201

    items = client.get("/api/editor/feedback", headers=headers).json()
    item = next(i for i in items if i["form"]["id"] == form["id"])
    assert item["community"] == "disputed"
    assert item["regions"] == {"UA-77": [0, 3]}
    assert [r["message"] for r in item["reports"]] == ["Так не кажуть"]
    assert items[0]["community"] == "disputed"  # disputed words come first

    report_id = item["reports"][0]["id"]
    assert (
        client.post(f"/api/editor/reports/{report_id}/resolve", headers=headers).status_code == 204
    )
    items = client.get("/api/editor/feedback", headers=headers).json()
    item = next(i for i in items if i["form"]["id"] == form["id"])
    assert item["reports"] == []


def test_ukraine_regions_for_the_voter() -> None:
    regions = client.get("/api/regions/ukraine").json()
    assert len(regions) >= 25
    assert all(r["code"].startswith("UA-") for r in regions)
