"""Regional words of other languages' dialect areas (German Brötchen / Schrippe / Semmel,
Spanish palomitas / pochoclo ...) from data/regional_words_<language>.json:
{concept slug: {area code: word or [words, the most widespread first]}}. An optional
"_main": {concept slug: word} names the language's standard word where Wiktionary's first
translation is odd (popcorn: "piras" -> "palomitas"); regional words are compared with it.

Words become drafts ("pending", shown with "≈") under the source "Dialectio suggestions
(draft)", to be checked by speakers in the game and by editors. Re-runnable: earlier drafts
still in the file stay with their votes, drafts dropped from it are deleted; words an editor
approved are kept.

Run after `dialects` (which creates the areas):
    uv run python -m app.importers.regional_words [language ...]   (default: every file)
"""

import json
import sys

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.word_actions import EDITOR_SOURCE_LICENSE, EDITOR_SOURCE_URL, SUGGESTION_SOURCE_NAME
from app.db.session import SessionLocal
from app.importers.common import upsert_source
from app.importers.wikidata_lexemes import DATA_DIR
from app.models import PENDING, Concept, Form, Source, Variety


def load(language: str) -> None:
    words: dict[str, dict[str, str | list[str]]] = json.loads(
        (DATA_DIR / f"regional_words_{language}.json").read_text(encoding="utf-8")
    )
    words.pop("_comment", None)
    main_words: dict[str, str] = words.pop("_main", {})  # type: ignore[assignment]
    with SessionLocal() as session:
        source = upsert_source(
            session, SUGGESTION_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
        )
        areas = {
            v.code: v
            for v in session.scalars(select(Variety).where(Variety.code.like(f"{language}-%")))
        }
        # Earlier drafts still in the file stay (with their votes); the others go
        drafts = {
            (f.concept_id, f.variety_id, f.spelling): f
            for f in session.scalars(
                select(Form).where(
                    Form.variety_id.in_([v.id for v in areas.values()]),
                    Form.source_id == source.id,
                    Form.status == PENDING,
                )
            )
        }
        concepts = {
            c.slug: c for c in session.scalars(select(Concept).where(Concept.slug.in_(list(words))))
        }
        # Areas that already have a (checked) word for a concept keep it as their main word
        draft_ids = [f.id for f in drafts.values()]
        has_word = {
            (concept_id, variety_id)
            for concept_id, variety_id in session.execute(
                select(Form.concept_id, Form.variety_id).where(
                    Form.variety_id.in_([v.id for v in areas.values()]),
                    Form.id.not_in(draft_ids),
                )
            )
        }
        added = 0
        for slug, by_area in words.items():
            concept = concepts.get(slug)
            if concept is None:
                print(f"  unknown concept {slug}, skipped")
                continue
            for area, value in by_area.items():
                variety = areas.get(area)
                if variety is None:
                    print(f"  unknown area {area}, run the dialects importer first")
                    continue
                # An area can have several words, the most widespread first
                spellings = [value] if isinstance(value, str) else value
                for index, word in enumerate(spellings):
                    primary = index == 0 and (concept.id, variety.id) not in has_word
                    kept = drafts.pop((concept.id, variety.id, word.strip()), None)
                    if kept is not None:
                        kept.is_primary = primary
                        continue
                    session.add(
                        Form(
                            concept=concept,
                            variety=variety,
                            spelling=word.strip(),
                            is_primary=primary,
                            status=PENDING,
                            source=source,
                        )
                    )
                    added += 1
        if drafts:
            session.execute(delete(Form).where(Form.id.in_([f.id for f in drafts.values()])))
        session.flush()
        fixed = set_main_words(session, language, main_words, source)
        session.commit()
    print(
        f"{language}: added {added} regional draft words for {len(concepts)} concepts, "
        f"{fixed} main words set."
    )


def set_main_words(
    session: Session, language: str, main_words: dict[str, str], source: Source
) -> int:
    """Make the given word the language's main word for the concept (adding it as a draft if
    the language doesn't have it)."""
    variety = session.scalar(select(Variety).where(Variety.code == language))
    concepts = {
        c.slug: c
        for c in session.scalars(select(Concept).where(Concept.slug.in_(list(main_words))))
    }
    for slug, word in main_words.items():
        concept = concepts.get(slug)
        if concept is None or variety is None:
            print(f"  unknown concept {slug} or language {language}, main word skipped")
            continue
        forms = list(
            session.scalars(
                select(Form).where(Form.concept_id == concept.id, Form.variety_id == variety.id)
            )
        )
        match = next((f for f in forms if f.spelling.lower() == word.lower()), None)
        for form in forms:
            form.is_primary = form is match
        if match is None:
            session.add(
                Form(
                    concept=concept,
                    variety=variety,
                    spelling=word,
                    is_primary=True,
                    status=PENDING,
                    source=source,
                )
            )
    return len(concepts)


def main(*languages: str) -> None:
    files = sorted(DATA_DIR.glob("regional_words_*.json"))
    for language in languages or [f.stem.removeprefix("regional_words_") for f in files]:
        load(language)


if __name__ == "__main__":
    main(*sys.argv[1:])
