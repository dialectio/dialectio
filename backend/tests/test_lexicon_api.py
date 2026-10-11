"""Integration tests against the local database with imported data.

Skipped when the database is not reachable or the importers have not been run.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db.session import engine
from app.main import app


def _has_data() -> bool:
    try:
        with engine.connect() as conn:
            return bool(conn.execute(text("SELECT EXISTS (SELECT 1 FROM form)")).scalar())
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _has_data(), reason="database with imported data required")

client = TestClient(app)


def search(q: str, **params: str) -> list[dict]:
    response = client.get("/api/search", params={"q": q, **params})
    assert response.status_code == 200
    return response.json()


def test_search_finds_same_concept_from_any_language() -> None:
    concept_ids = {search(q)[0]["concept"]["wikidata_id"] for q in ("water", "Wasser", "woda")}
    assert concept_ids == {"Q283"}


def test_search_prefers_requested_language_on_shared_spelling() -> None:
    assert search("вода", prefer="ukr")[0]["matched_language_en"] == "Ukrainian"
    assert search("вода", prefer="rus")[0]["matched_language_en"] == "Russian"


def test_search_treats_like_wildcards_literally() -> None:
    assert search("%") == []


def test_concept_detail_has_forms_and_map_labels() -> None:
    concept_id = search("water")[0]["concept"]["id"]
    detail = client.get(f"/api/concepts/{concept_id}").json()

    english = next(lang for lang in detail["languages"] if lang["iso639_3"] == "eng")
    assert english["forms"][0]["spelling"] == "water"
    assert english["forms"][0]["is_primary"]
    assert "GBR" in english["region_codes"]

    labels = {
        f["properties"]["code"]: f["properties"]["text"] for f in detail["labels"]["features"]
    }
    # Ukrainian first; Crimean Tatar is also mapped to Ukraine at country level
    assert labels["UKR"].split(" / ")[0] == "вода"


def test_concept_detail_404() -> None:
    assert client.get("/api/concepts/999999999").status_code == 404


def test_country_vector_tile() -> None:
    response = client.get("/api/regions/tiles/0/0/0.mvt")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.mapbox-vector-tile"
    assert len(response.content) > 1000
    # Layer name and attribute names are stored as strings inside the protobuf
    assert b"countries" in response.content and b"UKR" in response.content


def test_vector_tile_out_of_range() -> None:
    assert client.get("/api/regions/tiles/1/2/0.mvt").status_code == 404


def test_labels_use_curated_point_and_rank() -> None:
    concept_id = search("water")[0]["concept"]["id"]
    labels = client.get(f"/api/concepts/{concept_id}").json()["labels"]["features"]
    russia = next(f for f in labels if f["properties"]["code"] == "RUS")
    lng, lat = russia["geometry"]["coordinates"]
    assert lng < 60  # European Russia, not the middle of Siberia
    ranks = [f["properties"]["rank"] for f in labels]
    assert ranks == sorted(ranks)


def test_concept_by_slug_and_listing() -> None:
    water = client.get("/api/concepts/by-slug/water").json()
    assert water["wikidata_id"] == "Q283"
    assert water["slug"] == "water"
    assert client.get("/api/concepts/by-slug/no-such-word").status_code == 404

    slugs = {c["slug"] for c in client.get("/api/concepts").json()}
    assert {"water", "bark-q38681", "bark-q184453"} <= slugs


def test_region_labels_show_dialect_words() -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Concept, Form, Variety

    with SessionLocal() as session:
        concept = session.scalar(select(Concept).where(Concept.wikidata_id == "Q283"))
        hutsul = session.scalar(select(Variety).where(Variety.code == "ukr-hutsul"))
        form = Form(concept=concept, variety=hutsul, spelling="тестводиця", is_primary=True)
        session.add(form)
        session.commit()
        form_id = form.id
    try:
        labels = {
            f["properties"]["code"]: f["properties"]
            for f in client.get("/api/concepts/by-slug/water").json()["labels"]["features"]
        }
        # Hutsul is mapped to Ivano-Frankivsk, Chernivtsi and Transcarpathia
        assert labels["UA-26"]["text"] == "тестводиця"
        assert labels["UA-26"]["dialect"] and labels["UA-26"]["parent_code"] == "UKR"
        # other oblasts inherit the standard Ukrainian word; Crimea adds Crimean Tatar
        assert labels["UA-63"]["text"] == "вода" and not labels["UA-63"]["dialect"]
        assert labels["UA-43"]["text"].split(" / ")[0] == "вода"
        assert len(labels["UA-43"]["text"].split(" / ")) == 2
    finally:
        with SessionLocal() as session:
            session.delete(session.get(Form, form_id))
            session.commit()


def test_stats_count_public_data_and_list_sources() -> None:
    stats = client.get("/api/stats").json()
    assert stats["concepts"] > 100
    assert stats["languages"] > 40
    assert stats["dialects"] >= 15
    names = {s["name"] for s in stats["sources"]}
    assert {"Wikidata Lexemes", "Wikimedia Commons"} <= names
    assert stats["words"] == sum(s["words"] for s in stats["sources"])


def test_featured_concepts_have_several_dialect_words() -> None:
    featured = client.get("/api/concepts/featured", params={"limit": 5}).json()
    assert 0 < len(featured) <= 5
    assert all(len(c["examples"]) >= 2 for c in featured)
    counts = [len(c["examples"]) for c in featured]
    assert counts == sorted(counts, reverse=True)


def test_concept_links_to_related_word_pages() -> None:
    detail = client.get("/api/concepts/by-slug/water").json()
    slugs = [link["slug"] for link in detail["related"]]
    assert "water" not in slugs
    assert len(slugs) == len(set(slugs)) >= 3


def test_dialect_list_and_page() -> None:
    dialects = client.get("/api/dialects").json()
    codes = {d["code"] for d in dialects}
    assert {"ukr-hutsul", "ukr-lemko", "ukr-southwest"} <= codes

    hutsul = client.get("/api/dialects/ukr-hutsul").json()
    assert hutsul["parent_code"] == "ukr-southwest"
    assert "UA-26" in {r["code"] for r in hutsul["regions"]}
    west, south, east, north = hutsul["bounds"]
    assert west < east and south < north
    assert hutsul["words"] == len(hutsul["words_list"]) > 0
    assert client.get("/api/dialects/ukr-southwest").status_code == 404  # a group, not a dialect
    assert client.get("/api/dialects/nope").status_code == 404


def test_dialect_word_page() -> None:
    words = client.get("/api/dialect-words").json()
    assert "бараболя" in words
    assert "картопля" not in words  # standard Ukrainian words have no dialect-word page

    page = client.get("/api/dialect-words/Бараболя").json()  # case-insensitive
    meaning = next(m for m in page["meanings"] if m["slug"] == "potato")
    assert meaning["standard"] == "картопля"
    assert {"ukr-podillian", "ukr-dniester"} <= {d["code"] for d in meaning["dialects"]}
    assert "бульба" in {o["word"] for o in meaning["others"]}
    assert all(isinstance(d["form_id"], int) and "votes_yes" in d for d in meaning["dialects"])
    assert page["regions"] and page["bounds"]
    assert client.get("/api/dialect-words/немаєтакогослова").status_code == 404


def test_dialect_word_audio_is_not_repeated() -> None:
    for meaning in client.get("/api/dialect-words/бараболя").json()["meanings"]:
        urls = [a["url"] for a in meaning["audio"]]
        assert len(urls) == len(set(urls))
