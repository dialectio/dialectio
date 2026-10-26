"""The community page: totals, what the map holds, dialects that need checking."""

from fastapi.testclient import TestClient

from app.main import app
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)

client = TestClient(app)


def test_community_shows_the_map_and_where_help_is_needed() -> None:
    community = client.get("/api/community").json()
    numbers = community["map"]
    assert numbers["words"] > 100_000 and numbers["languages"] > 50
    assert numbers["dialects"] > 10 and numbers["pages"] > 1000
    unchecked = [d["words"] for d in community["needs_help"]]
    assert unchecked and unchecked == sorted(unchecked, reverse=True)
    assert all(d["code"].count("-") >= 1 for d in community["needs_help"])
