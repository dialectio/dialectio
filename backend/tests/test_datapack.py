"""Data packs: export → remove → apply brings words back; people's words and votes survive."""

import uuid
from pathlib import Path

from sqlalchemy import delete, select

from app.api.word_actions import EDITOR_SOURCE_LICENSE, EDITOR_SOURCE_NAME, EDITOR_SOURCE_URL
from app.db.session import SessionLocal
from app.importers import datapack
from app.importers.common import upsert_source
from app.models import APPROVED, Concept, Form, Source, Variety, Vote
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)


def make_concept(slug: str) -> None:
    with SessionLocal() as session:
        concept = Concept(slug=slug, gloss_en="test pack thing", gloss_uk="тестова річ")
        session.add(concept)
        imported = upsert_source(session, "Test import", None, "CC0")
        ukr = session.scalar(select(Variety).where(Variety.code == "ukr"))
        eng = session.scalar(select(Variety).where(Variety.code == "eng"))
        session.add_all(
            [
                Form(
                    concept=concept,
                    variety=ukr,
                    spelling="тестріч",
                    ipa="t",
                    is_primary=True,
                    status=APPROVED,
                    source=imported,
                ),
                Form(
                    concept=concept,
                    variety=eng,
                    spelling="testthing",
                    is_primary=True,
                    status=APPROVED,
                    source=imported,
                ),
            ]
        )
        session.commit()


def words(slug: str) -> dict[str, tuple[str | None, bool]]:
    with SessionLocal() as session:
        forms = session.scalars(select(Form).join(Concept).where(Concept.slug == slug)).all()
        return {f.spelling: (f.ipa, f.is_primary) for f in forms}


def test_round_trip_keeps_people_words_and_votes(tmp_path: Path) -> None:
    slug = f"test-pack-{uuid.uuid4().hex[:8]}"
    pack = tmp_path / "pack.zip"
    try:
        make_concept(slug)
        datapack.export(pack, [slug], [])
        datapack.remove([slug])
        assert words(slug) == {}

        datapack.apply(pack)
        assert words(slug) == {"тестріч": ("t", True), "testthing": (None, True)}

        # An editor approves their own spelling and a visitor votes on the imported word
        with SessionLocal() as session:
            concept = session.scalar(select(Concept).where(Concept.slug == slug))
            ukr = session.scalar(select(Variety).where(Variety.code == "ukr"))
            editor = upsert_source(
                session, EDITOR_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
            )
            for form in session.scalars(select(Form).where(Form.concept_id == concept.id)):
                form.is_primary = False if form.variety_id == ukr.id else form.is_primary
            session.add(
                Form(
                    concept=concept,
                    variety=ukr,
                    spelling="наша річ",
                    is_primary=True,
                    status=APPROVED,
                    source=editor,
                )
            )
            eng_word = session.scalar(select(Form).where(Form.spelling == "testthing"))
            session.add(Vote(form_id=eng_word.id, value=1, voter=f"test-{slug}", weight=1))
            session.commit()
            voted = eng_word.id

        datapack.apply(pack)  # applying again must not undo people's choices
        assert words(slug)["наша річ"] == (None, True)
        assert words(slug)["тестріч"] == ("t", False)
        with SessionLocal() as session:
            assert session.scalar(select(Vote.form_id).where(Vote.voter == f"test-{slug}")) == voted
    finally:
        datapack.remove([slug])
        with SessionLocal() as session:
            session.execute(delete(Source).where(Source.name == "Test import"))
            session.commit()
