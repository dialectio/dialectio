"""Visitors' votes and error reports (need the local database with imported data)."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api import feedback, gold
from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models import GoldAnswer, Report, Vote, community_status
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)

client = TestClient(app)
TOKEN = "test-token"
# Voters made by these tests: their control-card answers are removed afterwards
_voters: list[str] = []


@pytest.fixture
def form() -> Iterator[dict]:
    """A public Ukrainian dialect word, with its votes and reports removed after the test."""
    detail = client.get("/api/concepts/by-slug/potato").json()
    word = next(
        f
        for lang in detail["languages"]
        if lang["kind"] == "dialect" and lang["code"].startswith("ukr-")
        for f in lang["forms"]
    )
    yield word
    with SessionLocal() as session:
        session.execute(delete(Vote).where(Vote.form_id == word["id"]))
        session.execute(delete(Report).where(Report.form_id == word["id"]))
        session.commit()


@pytest.fixture(autouse=True)
def forget_voters() -> Iterator[None]:
    yield
    with SessionLocal() as session:
        hashes = [gold.voter_hash(v) for v in _voters]
        session.execute(delete(GoldAnswer).where(GoldAnswer.voter.in_(hashes)))
        session.commit()
    _voters.clear()


def answer_quiz(voter: str, language: str = "ukr", right: bool = True) -> dict:
    """Answer the quiz's control cards (rightly or wrongly); the test reads the answers from
    the tokens with the server's own function."""
    _voters.append(voter)
    cards = client.get("/api/check/quiz", params={"voter": voter, "language": language}).json()
    result = {}
    for card in cards["cards"]:
        expected = gold.read_token(card["gold"])[2]
        value = expected if right else -expected
        result = client.post(
            "/api/check/gold", json={"voter": voter, "token": card["gold"], "value": value}
        ).json()
    return result


def guest() -> str:
    """A guest who passed the Ukrainian quiz: their votes count GUEST_WEIGHT."""
    voter = uuid.uuid4().hex
    assert answer_quiz(voter)["passed"]
    return voter


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
            "voter": voter or guest(),
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
    # A guest's vote weighs 0.25: confirming takes 20 of them (5 of weight)
    for _ in range(19):
        result = vote(form["id"], 1, region="UA-26")
    assert result["yes"] == 19 and result["community"] is None
    result = vote(form["id"], 1, region="UA-26")
    assert result == {"form_id": form["id"], "yes": 20, "no": 0, "community": "confirmed"}

    detail = client.get("/api/concepts/by-slug/potato").json()
    shown = next(f for lang in detail["languages"] for f in lang["forms"] if f["id"] == form["id"])
    assert shown["votes_yes"] == 20 and shown["community"] == "confirmed"


def test_votes_without_the_quiz_count_nothing(form: dict) -> None:
    for _ in range(20):
        result = vote(form["id"], 1, voter=uuid.uuid4().hex)
    assert result["yes"] == 20 and result["community"] is None


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

    for _ in range(12):  # 3 of weight
        vote(form["id"], -1, region="UA-77")
    sent = client.post("/api/reports", json={"form_id": form["id"], "message": "  Так не кажуть  "})
    assert sent.status_code == 201

    items = client.get("/api/editor/feedback", headers=headers).json()
    item = next(i for i in items if i["form"]["id"] == form["id"])
    assert item["community"] == "disputed"
    assert item["regions"] == {"UA-77": [0, 12]}
    assert [r["message"] for r in item["reports"]] == ["Так не кажуть"]
    assert items[0]["community"] == "disputed"  # disputed words come first

    report_id = item["reports"][0]["id"]
    assert (
        client.post(f"/api/editor/reports/{report_id}/resolve", headers=headers).status_code == 204
    )
    items = client.get("/api/editor/feedback", headers=headers).json()
    item = next(i for i in items if i["form"]["id"] == form["id"])
    assert item["reports"] == []


def test_regions_for_the_voter() -> None:
    regions = client.get("/api/regions/voter").json()
    by_code = {r["code"]: r for r in regions}
    ukraine = [r for r in regions if r["country"] == "UKR"]
    assert len(ukraine) >= 25 and all(r["code"].startswith("UA-") for r in ukraine)
    assert {"PL-PK", "SK-PV", "RO-MM"} <= set(by_code)  # Lemko, Hutsul areas
    assert by_code["GB-WLS"]["country"] == "GBR"  # Western European regions
    # Countries without regions on the map are offered as a whole
    assert by_code["BRA"]["country"] is None
    assert "UKR" not in by_code  # Ukraine has its oblasts instead


def test_check_game_decks_and_cards() -> None:
    decks = {d["code"]: d for d in client.get("/api/check/decks").json()}
    assert decks["ukr"]["words"] > 0
    # Ukrainian with all dialects, plus one deck per dialect
    assert decks["ukr-hutsul"]["kind"] == "dialect"
    assert decks["ukr"]["words"] >= decks["ukr-hutsul"]["words"]
    hutsul = client.get(
        "/api/check/cards", params={"voter": uuid.uuid4().hex, "deck": "ukr-hutsul", "limit": 30}
    ).json()
    words = [c for c in hutsul if not c["gold"]]  # control cards are mixed in
    assert words and all(c["variety_code"] == "ukr-hutsul" for c in words)
    assert any(c["gold"] for c in hutsul)

    voter = uuid.uuid4().hex
    cards = client.get("/api/check/cards", params={"voter": voter, "limit": 5}).json()
    assert 0 < len([c for c in cards if not c["gold"]]) <= 5
    assert all(c["variety_code"] == "ukr" or c["variety_code"].startswith("ukr-") for c in cards)

    first = cards[0]["form_id"]
    try:
        vote(first, 1, voter)
        again = client.get(
            "/api/check/cards",
            params={"voter": voter, "limit": 30, "skip": [c["form_id"] for c in cards[1:]]},
        ).json()
        ids = {c["form_id"] for c in again}
        assert first not in ids  # already voted
        assert not ids & {c["form_id"] for c in cards[1:]}  # skipped
    finally:
        with SessionLocal() as session:
            session.execute(delete(Vote).where(Vote.form_id == first))
            session.commit()

    polish = client.get("/api/check/cards", params={"voter": voter, "deck": "pol"}).json()
    assert polish and all(c["variety_code"] == "pol" for c in polish)


def test_votes_on_a_verified_word_are_usage_data() -> None:
    detail = client.get("/api/concepts/by-slug/water").json()
    word = next(f for lang in detail["languages"] if lang["code"] == "ukr" for f in lang["forms"])
    assert not word["unverified"]
    try:
        for _ in range(3):
            vote(word["id"], -1, region="UA-26")
        items = client.get("/api/editor/feedback", headers={"X-Editor-Token": TOKEN}).json()
        item = next(i for i in items if i["form"]["id"] == word["id"])
        assert item["no"] == 3 and item["community"] is None  # not "disputed"
        assert item["regions"] == {"UA-26": [0, 3]}
    finally:
        with SessionLocal() as session:
            session.execute(delete(Vote).where(Vote.form_id == word["id"]))
            session.commit()


def test_concepts_have_ukrainian_descriptions() -> None:
    detail = client.get("/api/concepts/by-slug/drinking-glass").json()
    assert detail["description_uk"]


def test_missing_searches_are_counted_for_the_editor() -> None:
    headers = {"X-Editor-Token": TOKEN}
    query = f"немаєтакого{uuid.uuid4().hex[:6]}"
    try:
        for text_ in (query, f"  {query.upper()} "):
            assert client.post("/api/missing", json={"q": text_}).status_code == 204
        assert client.post("/api/missing", json={"q": "12"}).status_code == 204  # ignored
        items = client.get("/api/editor/missing", headers=headers).json()
        mine = next(i for i in items if i["query"] == query)
        assert mine["count"] == 2
        assert not any(i["query"] == "12" for i in items)
    finally:
        assert client.delete(f"/api/editor/missing/{query}", headers=headers).status_code == 204
    assert not any(
        i["query"] == query for i in client.get("/api/editor/missing", headers=headers).json()
    )


def test_community_page_counts_votes_by_region(form: dict) -> None:
    before = client.get("/api/community").json()
    vote(form["id"], 1, region="UA-26")
    after = client.get("/api/community").json()
    assert after["totals"]["votes"] == before["totals"]["votes"] + 1
    assert after["totals"]["voters"] == before["totals"]["voters"] + 1
    regions = {r["code"]: r["votes"] for r in after["regions"]}
    old = {r["code"]: r["votes"] for r in before["regions"]}
    assert regions["UA-26"] == old.get("UA-26", 0) + 1
    # The word is a dialect word, so its dialect is among the most checked ones
    assert after["dialects"] and after["dialects"][0]["votes"] >= 1


def test_regional_languages_are_decks() -> None:
    decks = {d["code"]: d for d in client.get("/api/check/decks").json()}
    assert decks["cym"]["kind"] == "regional" and decks["cym"]["words"] > 100
    cards = client.get(
        "/api/check/cards", params={"voter": uuid.uuid4().hex, "deck": "cym", "limit": 5}
    ).json()
    words = [c for c in cards if not c["gold"]]
    assert len(words) == 5 and all(c["variety_code"] == "cym" for c in words)


def test_control_cards_hide_their_answer_and_count_once() -> None:
    voter = uuid.uuid4().hex
    _voters.append(voter)
    cards = client.get("/api/check/quiz", params={"voter": voter, "language": "deu"}).json()
    assert len(cards["cards"]) == 3
    token = cards["cards"][0]["gold"]
    assert "1" not in token.split(".")[1:2]  # the answer is not written in the token
    answer = {"voter": voter, "token": token, "value": 1}
    assert client.post("/api/check/gold", json=answer).status_code == 200
    assert client.post("/api/check/gold", json=answer).status_code == 400  # used
    forged = {**answer, "token": token[:-1] + ("0" if token[-1] != "0" else "1")}
    assert client.post("/api/check/gold", json=forged).status_code == 400


def test_failing_the_quiz_means_waiting_a_day() -> None:
    voter = uuid.uuid4().hex
    assert not answer_quiz(voter, "deu", right=False)["passed"]
    status = client.get("/api/check/quiz/status", params={"voter": voter, "language": "deu"}).json()
    assert not status["passed"] and status["retry_after"] > 3600
    again = client.get("/api/check/quiz", params={"voter": voter, "language": "deu"}).json()
    assert again["cards"] == [] and again["retry_after"]
    # Passing one language says nothing about another
    assert answer_quiz(voter, "ukr")["passed"]
