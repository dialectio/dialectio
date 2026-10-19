"""Speaker tests, the weight of a speaker's votes, and the member's profile."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api import accounts, contribute, speaker
from app.api.gold import voter_hash
from app.db.session import SessionLocal
from app.main import app
from app.models import SPEAKER_WEIGHT, Form, User, Variety, Vote
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)


@pytest.fixture
def member() -> Iterator[TestClient]:
    """A freshly registered member; their account goes afterwards."""
    accounts._attempts.clear()
    contribute._recent.clear()
    with TestClient(app) as browser:
        response = browser.post(
            "/api/auth/register",
            json={
                "email": f"test-{uuid.uuid4().hex[:10]}@example.org",
                "password": "secret123",
                "name": "Mykola",
            },
        )
        assert response.status_code == 201
        yield browser
    with SessionLocal() as session:
        session.execute(delete(User).where(User.email.like("test-%@example.org")))
        session.commit()


def take_test(client: TestClient, answer: str = "right", variety: str = "ukr") -> dict:
    """Starts a test and answers every card: "right", "wrong" or "unsure"; the last result."""
    test = client.post("/api/speaker/tests", json={"variety": variety, "locale": "en"}).json()
    assert len(test["cards"]) == speaker.TEST_CARDS
    result = {}
    for card in test["cards"]:
        expected = speaker.read_token(test["id"], card["token"])[1]
        value = {"right": expected, "wrong": -expected, "unsure": 0}[answer]
        response = client.post(
            f"/api/speaker/tests/{test['id']}/answers",
            json={"token": card["token"], "value": value},
        )
        assert response.status_code == 200, response.text
        result = response.json()
    return result | {"test": test}


def test_cards_never_offer_the_real_meaning_as_a_trap(member: TestClient) -> None:
    with SessionLocal() as session:
        for locale in ("uk", "en"):
            for card in speaker.test_cards(session, 1, "ukr", locale):
                assert card.meaning and card.described == (locale == "uk")


def test_passing_makes_a_speaker_whose_votes_weigh_more(member: TestClient) -> None:
    languages = {v["code"]: v for v in member.get("/api/speaker/varieties").json()}
    assert "ukr" in languages and not languages["ukr"]["tested"]

    result = take_test(member)
    assert result["finished"] and result["passed"] and result["score"] == speaker.TEST_CARDS
    ukr = next(v for v in member.get("/api/speaker/varieties").json() if v["code"] == "ukr")
    assert ukr["tested"] and ukr["speaks"]
    again = member.post("/api/speaker/tests", json={"variety": "ukr", "locale": "en"})
    assert again.status_code == 409

    # A used card can't be answered twice
    card = result["test"]["cards"][0]
    used = member.post(
        f"/api/speaker/tests/{result['test']['id']}/answers",
        json={"token": card["token"], "value": 1},
    )
    assert used.status_code == 409

    # The test's answers passed the quiz too: a vote on a Hutsul word counts as a speaker's
    with SessionLocal() as session:
        form_id = session.scalar(
            select(Form.id)
            .join(Variety)
            .where(Variety.code == "ukr-hutsul", Form.status.in_(("approved", "pending")))
            .limit(1)
        )
    voter = uuid.uuid4().hex
    assert member.post(
        "/api/votes", json={"form_id": form_id, "value": 1, "voter": voter}
    ).is_success
    assert member.get("/api/profile").json()["votes"] == 1
    with SessionLocal() as session:
        mine = Vote.voter == voter_hash(f"user:{member.get('/api/auth/me').json()['id']}")
        weight = session.scalar(select(Vote.weight).where(Vote.form_id == form_id, mine))
        session.execute(delete(Vote).where(mine))
        session.commit()
    assert weight == SPEAKER_WEIGHT

    profile = member.get("/api/profile").json()
    assert profile["varieties"] == [
        {
            **{k: profile["varieties"][0][k] for k in ("name_en", "name_uk", "names", "kind")},
            "code": "ukr",
            "tested": True,
        }
    ]


def test_a_failed_test_waits_a_day(member: TestClient) -> None:
    result = take_test(member, "unsure")
    assert result["finished"] and result["passed"] is False and result["score"] == 0
    retry = member.post("/api/speaker/tests", json={"variety": "ukr", "locale": "en"}).json()
    assert retry["cards"] == [] and retry["retry_after"] > 3600 * 23


def test_guests_have_no_tests() -> None:
    with TestClient(app) as guest:
        response = guest.post("/api/speaker/tests", json={"variety": "ukr", "locale": "uk"})
    assert response.status_code == 401


def test_speaks_and_untested_dialects(member: TestClient) -> None:
    assert (
        member.put(
            "/api/speaker/speaks", json={"variety": "ukr-hutsul", "speaks": True}
        ).status_code
        == 204
    )
    assert [v["code"] for v in member.get("/api/profile").json()["varieties"]] == ["ukr-hutsul"]
    # Too few checked Hutsul words for a test yet
    response = member.post("/api/speaker/tests", json={"variety": "ukr-hutsul", "locale": "uk"})
    assert response.status_code == 422
    member.put("/api/speaker/speaks", json={"variety": "ukr-hutsul", "speaks": False})
    assert member.get("/api/profile").json()["varieties"] == []


def test_contributions_carry_the_members_name(member: TestClient) -> None:
    water = member.get("/api/concepts/by-slug/water").json()["id"]
    sent = member.post(
        "/api/contributions",
        data={
            "concept_id": water,
            "variety": "ukr-hutsul",
            "spelling": "вудапроф",
            "consent": "true",
        },
    )
    assert sent.status_code == 201
    [mine] = member.get("/api/profile").json()["contributions"]
    assert mine["spelling"] == "вудапроф" and mine["status"] == "submitted"

    assert member.put("/api/profile/name", json={"name": "Mykola K."}).status_code == 204
    with SessionLocal() as session:
        form = session.scalar(select(Form).where(Form.spelling == "вудапроф"))
        assert form.contributor == "Mykola K."
    assert member.delete("/api/auth/me").status_code == 204
    with SessionLocal() as session:
        form = session.scalar(select(Form).where(Form.spelling == "вудапроф"))
        assert form.contributor is None and form.contributor_id is None
        session.delete(form)
        session.commit()
