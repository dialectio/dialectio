"""Accounts: sign up, sign in, votes as the member, deleting the account."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api import accounts, gold
from app.api.accounts import check_password, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import GoldAnswer, User, Vote
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A browser of its own (its own cookies); its account is removed afterwards."""
    with TestClient(app) as browser:
        yield browser
    with SessionLocal() as session:
        session.execute(delete(User).where(User.email.like("test-%@example.org")))
        session.commit()


@pytest.fixture(autouse=True)
def no_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(accounts, "_attempts", accounts.defaultdict(accounts.deque))


def email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.org"


def test_passwords_are_hashed() -> None:
    stored = hash_password("correct horse")
    assert stored.startswith("scrypt$") and "correct horse" not in stored
    assert check_password("correct horse", stored)
    assert not check_password("wrong horse", stored)
    assert not check_password("anything", None)


def test_sign_up_sign_in_sign_out(client: TestClient) -> None:
    address = email()
    assert client.get("/api/auth/me").json() is None
    signup = {"email": f" {address.upper()} ", "password": "secret123", "name": " Оксана "}
    created = client.post("/api/auth/register", json=signup)
    assert created.status_code == 201, created.text
    assert created.json()["email"] == address and created.json()["name"] == "Оксана"
    assert client.get("/api/auth/me").json()["email"] == address  # signed in by the cookie

    assert client.post("/api/auth/register", json=signup).status_code == 409  # taken
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json() is None

    wrong = client.post("/api/auth/login", json={"email": address, "password": "nope"})
    assert wrong.status_code == 401
    right = client.post("/api/auth/login", json={"email": address, "password": "secret123"})
    assert right.status_code == 200 and client.get("/api/auth/me").json()["name"] == "Оксана"


def test_bad_sign_ups_are_rejected(client: TestClient) -> None:
    def sign_up(**fields: str) -> int:
        data = {"email": email(), "password": "secret123", "name": "A"} | fields
        return client.post("/api/auth/register", json=data).status_code

    assert sign_up(email="not-an-email") == 422
    assert sign_up(password="short") == 422
    assert sign_up(website="spam.example") == 400  # honeypot


def test_a_member_votes_as_themselves_with_more_weight(client: TestClient) -> None:
    client.post(
        "/api/auth/register", json={"email": email(), "password": "secret123", "name": "Петро"}
    )
    member = client.get("/api/auth/me").json()
    browser_id = uuid.uuid4().hex
    # The quiz, answered right: kept under the member, not the browser
    quiz = client.get("/api/check/quiz", params={"voter": browser_id, "language": "ukr"}).json()
    for card in quiz["cards"]:
        expected = gold.read_token(card["gold"])[2]
        client.post(
            "/api/check/gold", json={"voter": browser_id, "token": card["gold"], "value": expected}
        )
    detail = client.get("/api/concepts/by-slug/potato").json()
    form = next(
        f for lang in detail["languages"] if lang["code"].startswith("ukr-") for f in lang["forms"]
    )
    another_browser = uuid.uuid4().hex  # the same member on another device
    client.post("/api/votes", json={"form_id": form["id"], "value": 1, "voter": another_browser})
    with SessionLocal() as session:
        voter = gold.voter_hash(f"user:{member['id']}")
        weight = session.query(Vote.weight).filter_by(form_id=form["id"], voter=voter).scalar()
        assert weight == 0.5
        session.execute(delete(Vote).where(Vote.voter == voter))
        session.execute(delete(GoldAnswer).where(GoldAnswer.voter == voter))
        session.commit()


def test_deleting_the_account(client: TestClient) -> None:
    client.post(
        "/api/auth/register", json={"email": email(), "password": "secret123", "name": "Ірина"}
    )
    assert client.delete("/api/auth/me").status_code == 204
    assert client.get("/api/auth/me").json() is None
    assert client.delete("/api/auth/me").status_code == 401
