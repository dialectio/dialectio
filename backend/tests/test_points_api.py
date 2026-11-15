"""Points on the map: members' words where they say them, visible from a zoom by weight."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api import accounts, contribute, feedback
from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models import Form, FormChange, User, Vote
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)

TOKEN = "test-token"
EDITOR = {"X-Editor-Token": TOKEN}
WORD = "точкатест"


@pytest.fixture(autouse=True)
def setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "editor_token", TOKEN)
    contribute._recent.clear()
    feedback._recent.clear()
    yield
    with SessionLocal() as session:
        session.execute(delete(Form).where(Form.spelling == WORD))
        session.execute(delete(User).where(User.email.like("test-%@example.org")))
        session.commit()


def new_member() -> TestClient:
    accounts._attempts.clear()
    browser = TestClient(app)
    response = browser.post(
        "/api/auth/register",
        json={
            "email": f"test-{uuid.uuid4().hex[:10]}@example.org",
            "password": "secret123",
            "name": "Учасник",
        },
    )
    assert response.status_code == 201
    return browser


def settlement(client: TestClient, q: str) -> int:
    return client.get("/api/settlements", params={"q": q}).json()[0]["id"]


def add_word(member: TestClient, concept_id: int, settlement_id: int) -> None:
    response = member.post(
        "/api/contributions",
        data={
            "concept_id": str(concept_id),
            "variety": "ukr-hutsul",
            "spelling": WORD,
            "consent": "true",
            "settlement_id": str(settlement_id),
        },
    )
    assert response.status_code == 201, response.text


def points(client: TestClient, concept_id: int) -> list[dict]:
    collection = client.get(f"/api/concepts/{concept_id}/points").json()
    return [f["properties"] for f in collection["features"] if f["properties"]["spelling"] == WORD]


def add_votes(form_id: int, *votes: tuple[int, float, str | None]) -> None:
    with SessionLocal() as session:
        for value, weight, region in votes:
            session.add(
                Vote(
                    form_id=form_id,
                    value=value,
                    weight=weight,
                    region_code=region,
                    voter=uuid.uuid4().hex,
                )
            )
        session.commit()


def test_points_grow_with_members_and_local_votes() -> None:
    guest = TestClient(app)
    concept_id = guest.get("/api/concepts/by-slug/water").json()["id"]
    verkhovyna = settlement(guest, "Верховина")
    kosiv = settlement(guest, "Косів")

    # One member: visible only up close; the word is not in the word list yet
    add_word(new_member(), concept_id, verkhovyna)
    [point] = points(guest, concept_id)
    assert point["people"] == 1 and point["weight"] == 0.5 and point["level"] == 0
    assert point["unverified"] and point["place_names"]["uk"] == "Верховина"
    detail = guest.get(f"/api/concepts/{concept_id}").json()
    assert all(f["spelling"] != WORD for lang in detail["languages"] for f in lang["forms"])

    # A second member there: district zoom; one in Kosiv makes a point of its own
    add_word(new_member(), concept_id, verkhovyna)
    add_word(new_member(), concept_id, kosiv)
    found = {p["place_names"]["uk"]: p for p in points(guest, concept_id)}
    assert found["Верховина"]["people"] == 2 and found["Верховина"]["level"] == 1
    assert found["Косів"]["level"] == 0

    # "Yes" from people of the oblast lifts the points there, votes from elsewhere don't
    form_id = found["Верховина"]["form_id"]
    add_votes(form_id, (1, 2.0, "UA-26"), (1, 5.0, "UA-46"))
    found = {p["place_names"]["uk"]: p for p in points(guest, concept_id)}
    assert found["Верховина"]["weight"] == 3.0 and found["Верховина"]["level"] == 2

    # The word can be voted on and discussed before an editor sees it
    assert guest.get(f"/api/forms/{form_id}/discussion").json()["card"]["unverified"]

    # Enough "no" from the oblast hides its points
    add_votes(form_id, (-1, 6.0, "UA-26"))
    assert points(guest, concept_id) == []


def test_enough_weight_lets_a_word_into_the_word_list() -> None:
    guest = TestClient(app)
    concept_id = guest.get("/api/concepts/by-slug/water").json()["id"]
    add_word(new_member(), concept_id, settlement(guest, "Верховина"))
    form_id = points(guest, concept_id)[0]["form_id"]

    add_votes(form_id, (1, 3.0, None), (1, 3.0, "UA-26"))  # 0.5 + 6 < 8
    vote = {"form_id": form_id, "value": 1, "voter": "guest-browser-points"}
    assert guest.post("/api/votes", json=vote).is_success
    with SessionLocal() as session:
        assert session.get(Form, form_id).status == "submitted"

    add_votes(form_id, (1, 2.0, "UA-46"))
    assert guest.post("/api/votes", json={**vote, "value": -1}).is_success
    with SessionLocal() as session:
        form = session.get(Form, form_id)
        assert form.status == "pending"
        log = session.scalars(select(FormChange).where(FormChange.form_id == form_id)).all()
        assert [(c.action, c.actor) for c in log] == [("community", "community")]
    detail = guest.get(f"/api/concepts/{concept_id}").json()
    hutsul = next(lang for lang in detail["languages"] if lang["code"] == "ukr-hutsul")
    word = next(f for f in hutsul["forms"] if f["spelling"] == WORD)
    assert word["unverified"]

    # An editor's approval keeps the member as the source
    approved = guest.post(f"/api/editor/forms/{form_id}/approve", headers=EDITOR).json()
    assert approved["status"] == "approved" and approved["source"] == "Dialectio contributors"
