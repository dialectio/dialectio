"""Discussions of words: comments, reports and moderation."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api import accounts, feedback
from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models import EXPERT, Comment, ExpertRole, User
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)

TOKEN = "test-token"
EDITOR = {"X-Editor-Token": TOKEN}


@pytest.fixture(autouse=True)
def setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "editor_token", TOKEN)
    feedback._recent.clear()
    yield
    with SessionLocal() as session:
        # Their comments go with the accounts
        session.execute(delete(User).where(User.email.like("test-%@example.org")))
        session.commit()


def new_member(name: str) -> TestClient:
    accounts._attempts.clear()
    browser = TestClient(app)
    response = browser.post(
        "/api/auth/register",
        json={
            "email": f"test-{uuid.uuid4().hex[:10]}@example.org",
            "password": "secret123",
            "name": name,
        },
    )
    assert response.status_code == 201
    return browser


def ukrainian_water(client: TestClient) -> int:
    """The form id of the Ukrainian word for water."""
    detail = client.get("/api/concepts/by-slug/water").json()
    ukrainian = next(lang for lang in detail["languages"] if lang["code"] == "ukr")
    return ukrainian["forms"][0]["id"]


def say(client: TestClient, form_id: int, body: str, reply_to: int | None = None) -> dict:
    response = client.post(
        f"/api/forms/{form_id}/comments", json={"body": body, "reply_to": reply_to}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_discussion_opens_with_the_words_card_and_lists_comments() -> None:
    guest = TestClient(app)
    form_id = ukrainian_water(guest)
    discussion = guest.get(f"/api/forms/{form_id}/discussion").json()
    assert discussion["card"]["spelling"] == "вода"
    assert discussion["card"]["gloss_en"] == "water"
    assert discussion["can_moderate"] is False

    # Guests read but don't write
    response = guest.post(f"/api/forms/{form_id}/comments", json={"body": "привіт"})
    assert response.status_code == 401

    olena = new_member("Олена")
    first = say(olena, form_id, "  У нас кажуть «вода», а діди казали «водиця».  ")["comments"]
    mine = next(c for c in first if c["author"] == "Олена")
    assert mine["body"] == "У нас кажуть «вода», а діди казали «водиця»."
    assert mine["mine"] is True

    taras = new_member("Тарас")
    answer = say(taras, form_id, "І в нас так само", reply_to=mine["id"])["comments"]
    reply = next(c for c in answer if c["author"] == "Тарас")
    assert reply["reply_to"]["author"] == "Олена"
    assert next(c for c in answer if c["id"] == mine["id"])["mine"] is False

    # Empty comments are refused; the word's page counts the comments
    assert taras.post(f"/api/forms/{form_id}/comments", json={"body": "   "}).status_code == 422
    detail = guest.get("/api/concepts/by-slug/water").json()
    ukrainian = next(lang for lang in detail["languages"] if lang["code"] == "ukr")
    assert ukrainian["forms"][0]["comments"] >= 2

    # Authors edit and delete only their own
    edited = olena.patch(f"/api/comments/{mine['id']}", json={"body": "Виправила"}).json()
    assert next(c for c in edited["comments"] if c["id"] == mine["id"])["edited_at"]
    assert taras.delete(f"/api/comments/{mine['id']}").status_code == 404
    assert olena.delete(f"/api/comments/{mine['id']}").status_code == 204
    left = guest.get(f"/api/forms/{form_id}/discussion").json()["comments"]
    assert all(c["id"] != mine["id"] for c in left)
    assert next(c for c in left if c["id"] == reply["id"])["reply_to"] is None


def test_three_members_reports_hide_a_comment_until_an_editor_decides() -> None:
    guest = TestClient(app)
    form_id = ukrainian_water(guest)
    spammer = new_member("Спамер")
    comment = say(spammer, form_id, "купуйте тут")["comments"][-1]
    path = f"/api/comments/{comment['id']}/report"

    # A guest's report reaches the editors but does not hide it
    assert guest.post(path, json={"voter": "guest-browser-1", "reason": "спам"}).is_success
    for name in ("А", "Б"):
        reporter = new_member(name)
        assert reporter.post(path, json={"reason": "спам"}).is_success
        assert reporter.post(path, json={}).is_success  # twice counts once
    visible = guest.get(f"/api/forms/{form_id}/discussion").json()["comments"]
    assert any(c["id"] == comment["id"] for c in visible)

    assert new_member("В").post(path, json={}).is_success
    visible = guest.get(f"/api/forms/{form_id}/discussion").json()["comments"]
    assert all(c["id"] != comment["id"] for c in visible)

    listed = guest.get("/api/editor/comments", headers=EDITOR).json()
    item = next(c for c in listed if c["id"] == comment["id"])
    assert item["hidden"] and item["hidden_by"] == "reports" and len(item["reports"]) == 4
    assert guest.get("/api/editor/comments").status_code in (401, 403)

    # Restoring answers the reports
    restore = guest.post(f"/api/editor/comments/{comment['id']}/restore", headers=EDITOR)
    assert restore.status_code == 204
    visible = guest.get(f"/api/forms/{form_id}/discussion").json()["comments"]
    assert any(c["id"] == comment["id"] for c in visible)
    listed = guest.get("/api/editor/comments", headers=EDITOR).json()
    assert all(c["id"] != comment["id"] for c in listed)

    remove = guest.delete(f"/api/editor/comments/{comment['id']}", headers=EDITOR)
    assert remove.status_code == 204
    with SessionLocal() as session:
        assert session.get(Comment, comment["id"]) is None


def test_experts_of_the_variety_hide_and_restore_comments() -> None:
    guest = TestClient(app)
    form_id = ukrainian_water(guest)
    author = new_member("Автор")
    comment = say(author, form_id, "образливий текст")["comments"][-1]

    expert = new_member("Експерт")
    assert expert.post(f"/api/comments/{comment['id']}/hide").status_code == 403
    with SessionLocal() as session:
        user_id = expert.get("/api/auth/me").json()["id"]
        session.add(ExpertRole(user_id=user_id, variety_code="ukr", status=EXPERT))
        session.commit()

    discussion = expert.get(f"/api/forms/{form_id}/discussion").json()
    assert discussion["can_moderate"] is True
    hidden = expert.post(f"/api/comments/{comment['id']}/hide").json()
    assert next(c for c in hidden["comments"] if c["id"] == comment["id"])["hidden"] is True
    visible = guest.get(f"/api/forms/{form_id}/discussion").json()["comments"]
    assert all(c["id"] != comment["id"] for c in visible)

    # The expert's own comments carry the badge
    mine = say(expert, form_id, "Пояснення експерта")["comments"]
    assert next(c for c in mine if c["author"] == "Експерт")["badge"] == "expert"

    restored = expert.post(f"/api/comments/{comment['id']}/restore").json()
    assert next(c for c in restored["comments"] if c["id"] == comment["id"])["hidden"] is False
