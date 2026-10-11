"""Ukrainian concept descriptions written by Dialectio (data/descriptions_uk.json).

Wikidata has no Ukrainian description for some concepts; ours fill the gap. A Wikidata
description always wins: the Wikidata importer only falls back to these.

Run from backend/ after the Wikidata importer:  uv run python -m app.importers.descriptions
"""

import json
from functools import cache
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Concept

PATH = Path(__file__).parent / "data" / "descriptions_uk.json"


@cache
def own_descriptions() -> dict[str, str]:
    """{Wikidata item: Ukrainian description}"""
    data: dict[str, str] = json.loads(PATH.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def main() -> None:
    descriptions = own_descriptions()
    with SessionLocal() as session:
        missing = session.scalars(
            select(Concept).where(
                Concept.description_uk.is_(None), Concept.wikidata_id.in_(list(descriptions))
            )
        ).all()
        for concept in missing:
            concept.description_uk = descriptions[concept.wikidata_id]
        session.commit()
    print(f"Filled {len(missing)} Ukrainian descriptions.")


if __name__ == "__main__":
    main()
