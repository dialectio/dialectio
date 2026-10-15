"""Concept names fixed by Dialectio (data/glosses.json).

Some Wikidata labels make poor titles: plural ("качки"), scientific ("Rhopalocera",
"кінь свійський"), missing (numbers, pronouns) or identical for homonyms; Wiktionary's first
translation can be odd too ("кучерява капуста"). Our names win; keys are Wikidata items
("Q7386") or, for concepts from Wiktionary, slugs ("cauliflower"). The Wikidata and
Wiktionary importers apply them when they set names.

Run from backend/ after the Wikidata importer:  uv run python -m app.importers.glosses
"""

import json
from functools import cache
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Concept

PATH = Path(__file__).parent / "data" / "glosses.json"


@cache
def own_glosses() -> dict[str, dict[str, str]]:
    """{Wikidata item or slug: {"uk": name, "en": name}}; either key may be missing."""
    data = json.loads(PATH.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def apply_glosses(concept: Concept) -> None:
    glosses = own_glosses()
    names = glosses.get(concept.wikidata_id or "") or glosses.get(concept.slug or "", {})
    concept.gloss_uk = names.get("uk", concept.gloss_uk)
    concept.gloss_en = names.get("en", concept.gloss_en)


def main() -> None:
    glosses = own_glosses()
    with SessionLocal() as session:
        concepts = session.scalars(
            select(Concept).where(
                Concept.wikidata_id.in_(list(glosses)) | Concept.slug.in_(list(glosses))
            )
        ).all()
        for concept in concepts:
            apply_glosses(concept)
        session.commit()
    print(f"Applied names to {len(concepts)} concepts.")


if __name__ == "__main__":
    main()
