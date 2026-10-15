"""Names in the extra interface languages (Polish, German, Spanish, French).

- Concepts: the main word in that language ("ziemniak"); words shared by several concepts
  get the English name in brackets. Descriptions come from Wikidata where it has them.
- Languages: CLDR names (babel); Ukrainian dialects: data/dialect_names.json.
- Countries and regions: Natural Earth; Ukraine's oblasts get the word for "oblast".

    uv run --group import python -m app.importers.localize

Run after the other importers (it reads words, varieties and regions); re-runnable.
"""

import json
import re
from collections import Counter
from pathlib import Path

import shapefile
from babel import Locale
from sqlalchemy import select

from app.db.session import SessionLocal
from app.importers.common import RAW_DIR
from app.importers.languages import LANGUAGES
from app.importers.natural_earth_admin1 import merged_regions
from app.importers.wikidata_lexemes import WikimediaClient, chunks
from app.locales import EXTRA_LOCALES
from app.models import PUBLIC_STATUSES, Concept, Form, Region, Variety

DIALECT_NAMES = Path(__file__).parent / "data" / "dialect_names.json"
NATURAL_EARTH = RAW_DIR / "natural_earth"
COUNTRIES_FILE = NATURAL_EARTH / "ne_10m_admin_0_countries_ukr"
REGIONS_FILE = NATURAL_EARTH / "ne_10m_admin_1_states_provinces"

# Natural Earth names Ukraine's oblasts after their centre ("Lwiw") or by an adjective
# ("lwowski"); the word for "oblast" is added per language.
OBLAST = {
    "pl": lambda name: f"obwód {name}",
    "de": lambda name: f"Oblast {name}",
    "es": lambda name: f"óblast de {name}",
    "fr": lambda name: f"oblast {name}" if name.startswith("d'") else f"oblast de {name}",
}
# Regions that are not "oblast <centre>"
REGION_FIXES = {
    "UA-30": {"pl": "Kijów", "de": "Kiew", "es": "Kiev", "fr": "Kiev"},
    "UA-32": {
        "pl": "obwód kijowski",
        "de": "Oblast Kiew",
        "es": "óblast de Kiev",
        "fr": "oblast de Kiev",
    },
}
NOT_OBLASTS = {"UA-30", "UA-32", "UA-40", "UA-43"}  # Kyiv, Sevastopol, Crimea


def region_names() -> dict[str, dict[str, str]]:
    names: dict[str, dict[str, str]] = {}
    for record in shapefile.Reader(str(COUNTRIES_FILE), encoding="utf-8").iterRecords():
        attrs = record.as_dict()
        names[attrs["ADM0_A3"]] = {
            loc: attrs[f"NAME_{loc.upper()}"]
            for loc in EXTRA_LOCALES
            if attrs[f"NAME_{loc.upper()}"]
        }
    for record in shapefile.Reader(str(REGIONS_FILE), encoding="utf-8").iterRecords():
        attrs = record.as_dict()
        code = attrs["iso_3166_2"] or ""
        local = {loc: attrs[f"name_{loc}"] for loc in EXTRA_LOCALES if attrs[f"name_{loc}"]}
        if code.startswith("UA-") and code not in NOT_OBLASTS:
            local = {loc: OBLAST[loc](name) for loc, name in local.items()}
        names[code] = local | REGION_FIXES.get(code, {})
    # Regions merged from several units (Brittany, Sicily, Wales ...) have their own names
    for code, region in merged_regions().items():
        names[code] = {loc: region["names"][loc] for loc in EXTRA_LOCALES if loc in region["names"]}
    return names


def variety_names() -> dict[str, dict[str, str]]:
    cldr = {loc: Locale(loc).languages for loc in EXTRA_LOCALES}
    names = {
        lang.iso639_3: {
            loc: cldr[loc][lang.lemma_tag] for loc in EXTRA_LOCALES if lang.lemma_tag in cldr[loc]
        }
        for lang in LANGUAGES
    }
    dialects = json.loads(DIALECT_NAMES.read_text(encoding="utf-8"))
    dialects.pop("_comment", None)
    return names | dialects


def concept_glosses(session) -> dict[int, dict[str, str]]:
    """{concept id: {locale: name}} from each language's main word."""
    concepts = {c.id: c for c in session.scalars(select(Concept))}
    glosses: dict[int, dict[str, str]] = {c: {} for c in concepts}
    for locale, code in EXTRA_LOCALES.items():
        words = dict(
            session.execute(
                select(Form.concept_id, Form.spelling)
                .join(Variety, Variety.id == Form.variety_id)
                .where(Variety.code == code, Form.is_primary, Form.status.in_(PUBLIC_STATUSES))
                .order_by(Form.status)  # "approved" before "pending"
            ).all()
        )
        counts = Counter(words.values())
        for concept_id, word in words.items():
            if counts[word] > 1:
                # Several concepts share the word: tell them apart by the English name.
                hint = re.sub(r"\s*\((.*)\)$", r", \1", concepts[concept_id].gloss_en)
                word = f"{word} ({hint})"
            glosses[concept_id][locale] = word
    return glosses


def wikidata_descriptions(qids: list[str]) -> dict[str, dict[str, str]]:
    client = WikimediaClient()
    found: dict[str, dict[str, str]] = {}
    langs = ", ".join(f'"{loc}"' for loc in EXTRA_LOCALES)
    for batch in chunks(qids, 200):
        values = " ".join(f"wd:{q}" for q in batch)
        rows = client.sparql(f"""
            SELECT ?item ?description (LANG(?description) AS ?lang) WHERE {{
              VALUES ?item {{ {values} }}
              ?item schema:description ?description .
              FILTER(LANG(?description) IN ({langs}))
            }}""")
        for row in rows:
            qid = row["item"].rsplit("/", 1)[-1]
            found.setdefault(qid, {})[row["lang"]] = row["description"]
    return found


def main() -> None:
    with SessionLocal() as session:
        regions = region_names()
        for region in session.scalars(select(Region)):
            region.names = regions.get(region.code, {})
        varieties = variety_names()
        for variety in session.scalars(select(Variety)):
            variety.names = varieties.get(variety.code, {})
        glosses = concept_glosses(session)
        concepts = list(session.scalars(select(Concept)))
        for concept in concepts:
            concept.glosses = glosses.get(concept.id, {})
        session.commit()
        print(
            f"Names: {len(regions)} regions, {len(varieties)} varieties, {len(concepts)} concepts"
        )

        qids = [c.wikidata_id for c in concepts if c.wikidata_id]
        descriptions = wikidata_descriptions(qids)
        for concept in concepts:
            found = descriptions.get(concept.wikidata_id or "", {})
            # Ours (app.importers.definitions) stay where Wikidata has none
            ours = {
                locale: text
                for locale, text in (concept.descriptions or {}).items()
                if locale in (concept.description_origins or {}) and locale not in found
            }
            concept.descriptions = ours | found
            concept.description_origins = {
                locale: origin
                for locale, origin in (concept.description_origins or {}).items()
                if locale in ours
            }
        session.commit()
        print(f"Descriptions from Wikidata for {len(descriptions)} of {len(qids)} concepts")


if __name__ == "__main__":
    main()
