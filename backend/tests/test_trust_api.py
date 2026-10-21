"""Trusted speakers, experts and the change log."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api import accounts, trust
from app.api.gold import voter_hash
from app.api.word_actions import EDITOR_SOURCE_URL, SUGGESTION_SOURCE_NAME
from app.config import settings
from app.db.session import SessionLocal
from app.importers.common import upsert_source
from app.main import app
from app.models import (
    EXPERT_WEIGHT,
    PENDING,
    TRUSTED_WEIGHT,
    Concept,
    Form,
    FormChange,
    GoldAnswer,
    User,
    Variety,
    Vote,
)
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)
from tests.test_speaker_api import take_test

TOKEN = "test-token"


@pytest.fixture
def member(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A member who passed the Ukrainian speaker test; everything they caused goes after."""
    monkeypatch.setattr(settings, "editor_token", TOKEN)
    accounts._attempts.clear()
    with TestClient(app) as browser:
        browser.post(
            "/api/auth/register",
            json={
                "email": f"test-{uuid.uuid4().hex[:10]}@example.org",
                "password": "secret123",
                "name": "Vasyl",
            },
        )
        assert take_test(browser)["passed"]
        yield browser
    with SessionLocal() as session:
        session.execute(delete(Form).where(Form.spelling.like("тестслово%")))
        session.execute(delete(FormChange).where(FormChange.spelling.like("тестслово%")))
        session.execute(delete(User).where(User.email.like("test-%@example.org")))
        session.commit()


def member_id(client: TestClient) -> int:
    return client.get("/api/auth/me").json()["id"]


def draft(variety: str = "ukr-hutsul") -> int:
    """A draft word of the variety for the expert to review."""
    with SessionLocal() as session:
        form = Form(
            concept_id=session.scalar(select(Concept.id).where(Concept.slug == "water")),
            variety_id=session.scalar(select(Variety.id).where(Variety.code == variety)),
            spelling=f"тестслово{uuid.uuid4().hex[:6]}",
            status=PENDING,
            source=upsert_source(session, SUGGESTION_SOURCE_NAME, EDITOR_SOURCE_URL, "test"),
        )
        session.add(form)
        session.commit()
        return form.id


def test_trusted_after_enough_votes_and_right_control_answers(member: TestClient) -> None:
    user_id = member_id(member)
    voter = voter_hash(f"user:{user_id}")
    with SessionLocal() as session:
        assert not trust.language_trust(session, user_id, "ukr").trusted
        forms = session.scalars(
            select(Form.id)
            .join(Variety)
            .where(Variety.code == "ukr", Form.status == "approved")
            .limit(trust.TRUSTED_VOTES)
        ).all()
        session.add_all(Vote(form_id=f, value=1, voter=voter, weight=1.0) for f in forms)
        session.commit()
        state = trust.language_trust(session, user_id, "ukr")
        assert state.trusted and state.votes == trust.TRUSTED_VOTES and state.accuracy == 1
        user = session.get(User, user_id)
        assert trust.member_weight(session, user, "ukr-hutsul") == TRUSTED_WEIGHT

        # Wrong control answers take it away again
        session.add_all(GoldAnswer(voter=voter, language="ukr", correct=False) for _ in range(10))
        session.commit()
        assert not trust.language_trust(session, user_id, "ukr").trusted
        session.execute(delete(Vote).where(Vote.voter == voter))
        session.commit()


def test_expert_application_review_and_log(member: TestClient) -> None:
    editor = {"X-Editor-Token": TOKEN}
    form_id = draft()
    # Not an expert yet: no queue
    assert member.get("/api/expert/queue", params={"variety": "ukr-hutsul"}).status_code == 403
    note = {"variety": "ukr-hutsul", "note": "Born and live in Verkhovyna, Hutsul at home."}
    assert member.post("/api/expert/applications", json=note).status_code == 204

    applications = member.get("/api/editor/experts", headers=editor).json()
    mine = next(a for a in applications if a["user_id"] == member_id(member))
    assert mine["status"] == "applied" and "Verkhovyna" in mine["note"]
    decision = {"user_id": mine["user_id"], "variety": "ukr-hutsul", "status": "expert"}
    assert member.post("/api/editor/experts/decision", json=decision, headers=editor).is_success

    queue = member.get("/api/expert/queue", params={"variety": "ukr-hutsul"}).json()
    assert form_id in [item["form"]["id"] for item in queue]
    # Only Hutsul: another dialect's words are not theirs
    other = draft("ukr-boyko")
    assert member.post(f"/api/expert/forms/{other}/approve").status_code == 403

    fixed = member.post(
        f"/api/expert/forms/{form_id}/spelling", json={"spelling": "тестсловоґ"}
    ).json()
    assert fixed["spelling"] == "тестсловоґ"
    assert member.post(f"/api/expert/forms/{form_id}/approve").json()["status"] == "approved"
    # Approved words are the editors' to delete
    assert member.post(f"/api/expert/forms/{form_id}/reject").status_code == 409

    log = member.get("/api/expert/changes", params={"variety": "ukr-hutsul"}).json()
    assert [(c["action"], c["actor"]) for c in log[:2]] == [
        ("approve", "Vasyl"),
        ("spelling", "Vasyl"),
    ]
    assert log[1]["after"]["spelling"] == "тестсловоґ"
    with SessionLocal() as session:
        user = session.get(User, member_id(member))
        assert trust.member_weight(session, user, "ukr-hutsul") == EXPERT_WEIGHT
    profile = member.get("/api/profile").json()
    assert profile["roles"][0]["status"] == "expert" and profile["trust"][0]["speaker"]


def test_only_speakers_apply(member: TestClient) -> None:
    note = {"variety": "deu-bavarian", "note": "I lived in Munich for a year."}
    assert member.post("/api/expert/applications", json=note).status_code == 403


def test_editor_changes_are_logged(member: TestClient) -> None:
    editor = {"X-Editor-Token": TOKEN}
    form_id = draft()
    assert member.post(f"/api/editor/forms/{form_id}/approve", headers=editor).is_success
    log = member.get("/api/editor/changes", headers=editor).json()
    assert log[0]["action"] == "approve" and log[0]["actor"] == "editors"
    assert member.delete(f"/api/editor/forms/{form_id}", headers=editor).status_code == 204
    log = member.get("/api/editor/changes", headers=editor).json()
    assert log[0]["action"] == "delete" and log[0]["form_id"] is None
