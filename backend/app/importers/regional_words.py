"""Regional words of other languages' dialect areas (pilot: German Brötchen / Schrippe /
Semmel ...) from data/regional_words_<language>.json: {concept slug: {area code: word}}.

Words become drafts ("pending", shown with "≈") under the source "Dialectio suggestions
(draft)", to be checked by speakers in the game and by editors. Re-runnable: earlier drafts
of the language's areas are replaced; words an editor approved are kept.

Run after `dialects` (which creates the areas):
    uv run python -m app.importers.regional_words [language ...]   (default: every file)
"""

import json
import sys

from sqlalchemy import delete, select

from app.api.editor import EDITOR_SOURCE_LICENSE, EDITOR_SOURCE_URL, SUGGESTION_SOURCE_NAME
from app.db.session import SessionLocal
from app.importers.common import upsert_source
from app.importers.wikidata_lexemes import DATA_DIR
from app.models import PENDING, Concept, Form, Variety


def load(language: str) -> None:
    words: dict[str, dict[str, str]] = json.loads(
        (DATA_DIR / f"regional_words_{language}.json").read_text(encoding="utf-8")
    )
    words.pop("_comment", None)
    with SessionLocal() as session:
        source = upsert_source(
            session, SUGGESTION_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
        )
        areas = {
            v.code: v
            for v in session.scalars(select(Variety).where(Variety.code.like(f"{language}-%")))
        }
        session.execute(
            delete(Form).where(
                Form.variety_id.in_([v.id for v in areas.values()]),
                Form.source_id == source.id,
                Form.status == PENDING,
            )
        )
        concepts = {
            c.slug: c for c in session.scalars(select(Concept).where(Concept.slug.in_(list(words))))
        }
        # Areas that already have a (checked) word for a concept keep it as their main word
        has_word = {
            (concept_id, variety_id)
            for concept_id, variety_id in session.execute(
                select(Form.concept_id, Form.variety_id).where(
                    Form.variety_id.in_([v.id for v in areas.values()])
                )
            )
        }
        added = 0
        for slug, by_area in words.items():
            concept = concepts.get(slug)
            if concept is None:
                print(f"  unknown concept {slug}, skipped")
                continue
            for area, word in by_area.items():
                variety = areas.get(area)
                if variety is None:
                    print(f"  unknown area {area}, run the dialects importer first")
                    continue
                session.add(
                    Form(
                        concept=concept,
                        variety=variety,
                        spelling=word.strip(),
                        is_primary=(concept.id, variety.id) not in has_word,
                        status=PENDING,
                        source=source,
                    )
                )
                added += 1
        session.commit()
    print(f"{language}: added {added} regional draft words for {len(concepts)} concepts.")


def main(*languages: str) -> None:
    files = sorted(DATA_DIR.glob("regional_words_*.json"))
    for language in languages or [f.stem.removeprefix("regional_words_") for f in files]:
        load(language)


if __name__ == "__main__":
    main(*sys.argv[1:])
