"""Concept descriptions in the extra interface languages (pl, de, es, fr) where Wikidata has
none: the definition from that language's own Wiktionary, else a machine translation of the
English description.

Wiktionary: for the concept's main word in the language (Polish "zamek"), the meaning whose
English translations include the concept's English word ("castle" → "budynek warowny");
a word with a single meaning needs no translation to match. Extracts of the Polish, German,
Spanish and French Wiktionaries come from kaikki.org (~1.3 GB, downloaded once to
data/raw/wiktionary/).

Machine translation: Argos Translate (offline), run as a separate program because it pulls in
torch (needs `uv` on PATH; models are downloaded on first use). Marked "machine" in
`Concept.description_origins`, the site labels them. Ukrainian is left out: its machine
translations are too poor.

    uv run python -m app.importers.definitions [--no-machine] [--limit N]

Run after `wiktionary` and `localize`. Re-runnable: fills only missing descriptions.
"""

import argparse
import gzip
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import httpx2
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.importers.common import RAW_DIR, upsert_source
from app.locales import EXTRA_LOCALES
from app.models import Concept

DUMP_URL = "https://kaikki.org/dictionary/downloads/{locale}/{locale}-extract.jsonl.gz"
DUMP_DIR = RAW_DIR / "wiktionary"
ARGOS_SCRIPT = Path(__file__).parent / "tools" / "argos_translate.py"

WIKTIONARY = "wiktionary"
MACHINE = "machine"
SOURCE_LICENSE = "CC BY-SA 4.0"
MACHINE_SOURCE = "Machine-translated descriptions (Argos Translate, from English Wiktionary)"
MACHINE_URL = "https://github.com/argosopentech/argos-translate"

MAX_LENGTH = 300  # longer definitions are cut at a sentence or clause end
# Definitions that only point elsewhere ("zob. …", "→ …")
POINTER = re.compile(r"^(zob\.|zobacz|siehe|véase|voir|→|↑)", re.IGNORECASE)
# Inflected forms: "Participio de …", "pluriel de …", "Plural von …"
FORM_OF = re.compile(
    r"^(participio|gerundio|plural|femenino|masculino|participe|pluriel|féminin|masculin"
    r"|deuxième|troisième|première|singular|genitiv|dativ|akkusativ|nominativ)\b.*\b(de|du|von|des)\b",
    re.IGNORECASE,
)
# References to other meanings: "samiec psa (1.1)", "[2]"
SENSE_REFERENCE = re.compile(r"\s*[\(\[]\d+(\.\d+)?[\)\]]")

# Main word per concept in each language, and every English word of each concept
WORDS = text("""
    SELECT f.concept_id, v.code, f.spelling, f.is_primary
    FROM form f JOIN variety v ON v.id = f.variety_id
    WHERE v.code = ANY(:codes) AND f.status IN ('approved', 'pending')
""")


def source_name(locale: str) -> str:
    return f"Wiktionary definitions ({locale}.wiktionary.org)"


def download(locale: str) -> Path:
    path = DUMP_DIR / f"{locale}-extract.jsonl.gz"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = DUMP_URL.format(locale=locale)
        print(f"Downloading {url} ...")
        with httpx2.stream("GET", url, follow_redirects=True, timeout=None) as response:
            response.raise_for_status()
            with path.open("wb") as out:
                for chunk in response.iter_bytes(1 << 20):
                    out.write(chunk)
    return path


def sense_numbers(ref: object) -> list[str]:
    """ "1", 2, "1,3", "4–5", "1.1" -> the sense numbers it names."""
    numbers = []
    for part in re.split(r"\s*,\s*", str(ref)):
        span = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", part)
        if span:
            numbers += [str(n) for n in range(int(span[1]), int(span[2]) + 1)]
        elif part:
            numbers.append(part.strip())
    return numbers


def clean(gloss: str) -> str | None:
    gloss = SENSE_REFERENCE.sub("", gloss).strip(" .…")
    if not gloss or POINTER.match(gloss):
        return None
    if len(gloss) > MAX_LENGTH:
        cut = max(gloss.rfind(mark, 0, MAX_LENGTH) for mark in (". ", "; ", ", "))
        gloss = gloss[:cut] if cut > 40 else gloss[:MAX_LENGTH].rsplit(" ", 1)[0] + "…"
    return gloss


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w{4,}", text.lower())}


def same_sense(label: str, senses: list[dict]) -> dict | None:
    """The sense a translation table's label describes: French labels shorten the definition
    ("Établissement pour les très jeunes enfants"), so pick the one sharing most words."""
    words = content_words(re.sub(r"^(\([^)]*\)\s*)+", "", label).split(":")[-1])
    best, overlap = None, 0
    for sense in senses:
        common = len(words & content_words(sense["glosses"][-1]))
        if common > overlap:
            best, overlap = sense, common
    return best


def is_form_of(sense: dict) -> bool:
    """ "Participio de responsabilizar", "pluriel de …": grammar, not a definition."""
    return (
        "form_of" in sense
        or "form-of" in sense.get("tags", [])
        or bool(FORM_OF.match(sense["glosses"][-1]))
    )


def entry_definitions(entry: dict, english: set[str]) -> tuple[list[str], list[str]]:
    """(definitions of the meanings translated by one of `english`, all definitions)."""
    senses = [s for s in entry.get("senses", []) if s.get("glosses") and not is_form_of(s)]
    # Polish, German and Spanish number their senses and point translations at the numbers;
    # French numbers only its translation groups, so there the group's label decides.
    by_number = {str(s["sense_index"]): s for s in senses if "sense_index" in s}
    matched: list[dict] = []
    for tr in entry.get("translations", []):
        if tr.get("lang_code") != "en" or tr.get("word", "").lower() not in english:
            continue
        found = None
        if by_number and "sense_index" in tr:
            numbers = sense_numbers(tr["sense_index"])
            found = next((by_number[n] for n in numbers if n in by_number), None)
        if found is None and tr.get("sense"):
            found = same_sense(tr["sense"], senses)
        if found is not None and found not in matched:
            matched.append(found)
    definitions = [s["glosses"][-1] for s in senses]
    return [s["glosses"][-1] for s in matched], definitions


def wiktionary_definitions(
    locale: str, wanted: dict[str, list[tuple[int, set[str]]]]
) -> dict[int, str]:
    """{concept id: definition} for the wanted {word: [(concept id, English words)]}."""
    matches: dict[int, list[str]] = defaultdict(list)
    all_senses: dict[int, list[str]] = defaultdict(list)
    word_pattern = re.compile(r'"word": "((?:[^"\\]|\\.)*)"')
    with gzip.open(download(locale), "rt", encoding="utf-8") as lines:
        for line in lines:
            if not any(w in wanted for w in word_pattern.findall(line)):
                continue
            entry = json.loads(line)
            if entry.get("lang_code") != locale or entry.get("word") not in wanted:
                continue
            for concept_id, english in wanted[entry["word"]]:
                matched, definitions = entry_definitions(entry, english)
                matches[concept_id] += matched
                all_senses[concept_id] += definitions

    found = {}
    for concept_id in set(matches) | set(all_senses):
        # The first matching meaning; a word with one meaning is that meaning
        candidates = matches[concept_id] or (
            all_senses[concept_id] if len(all_senses[concept_id]) == 1 else []
        )
        for candidate in candidates:
            definition = clean(candidate)
            if definition:
                found[concept_id] = definition
                break
    return found


def machine_translations(texts: list[str], locales: list[str]) -> dict[str, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        request, result = Path(tmp) / "in.json", Path(tmp) / "out.json"
        request.write_text(json.dumps({"to": locales, "texts": texts}), encoding="utf-8")
        subprocess.run(
            ["uvx", "--python", "3.11", "--from", "argostranslate", "python",
             str(ARGOS_SCRIPT), str(request), str(result)],
            check=True,
        )  # fmt: skip
        return json.loads(result.read_text(encoding="utf-8"))


def main(machine: bool, limit: int | None) -> None:
    codes = {iso: locale for locale, iso in EXTRA_LOCALES.items()}
    with SessionLocal() as session:
        concepts = {c.id: c for c in session.scalars(select(Concept).order_by(Concept.id))}
        if limit:
            concepts = dict(list(concepts.items())[:limit])
        english: dict[int, set[str]] = defaultdict(set)
        main_word: dict[str, dict[int, str]] = defaultdict(dict)
        for concept_id, code, spelling, is_primary in session.execute(
            WORDS, {"codes": [*codes, "eng"]}
        ):
            if concept_id not in concepts:
                continue
            if code == "eng":
                english[concept_id].add(spelling.lower())
            elif is_primary:
                main_word[codes[code]][concept_id] = spelling
        for concept in concepts.values():
            english[concept.id].add(re.sub(r"\s*\(.*\)$", "", concept.gloss_en).lower())

        def missing(locale: str) -> list[Concept]:
            return [c for c in concepts.values() if not (c.descriptions or {}).get(locale)]

        def store(concept: Concept, locale: str, description: str, origin: str) -> None:
            concept.descriptions = {**(concept.descriptions or {}), locale: description[:500]}
            concept.description_origins = {**(concept.description_origins or {}), locale: origin}

        for locale in EXTRA_LOCALES:
            wanted: dict[str, list[tuple[int, set[str]]]] = defaultdict(list)
            for concept in missing(locale):
                word = main_word[locale].get(concept.id)
                if word:
                    wanted[word].append((concept.id, english[concept.id]))
            definitions = wiktionary_definitions(locale, wanted)
            for concept_id, definition in definitions.items():
                store(concepts[concept_id], locale, definition, WIKTIONARY)
            upsert_source(
                session, source_name(locale), f"https://{locale}.wiktionary.org/", SOURCE_LICENSE
            )
            session.commit()
            print(f"{locale}: {len(definitions)} definitions from Wiktionary")

        if machine:
            todo = {
                locale: [c for c in missing(locale) if c.description_en] for locale in EXTRA_LOCALES
            }
            texts = sorted({c.description_en for group in todo.values() for c in group})
            print(f"Machine-translating {len(texts)} English descriptions ...")
            translated = machine_translations(texts, list(EXTRA_LOCALES))
            for locale, group in todo.items():
                by_text = dict(zip(texts, translated[locale], strict=True))
                for concept in group:
                    if by_text[concept.description_en].strip():
                        store(concept, locale, by_text[concept.description_en].strip(), MACHINE)
                print(f"{locale}: {len(group)} machine translations")
            upsert_source(session, MACHINE_SOURCE, MACHINE_URL, SOURCE_LICENSE)
            session.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-machine", action="store_true", help="only Wiktionary definitions")
    parser.add_argument("--limit", type=int, help="only the first N concepts (for a trial)")
    args = parser.parse_args()
    main(machine=not args.no_machine, limit=args.limit)
