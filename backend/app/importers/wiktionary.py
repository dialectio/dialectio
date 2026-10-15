"""Import words from English Wiktionary translation tables (via kaikki.org / wiktextract).

For the most frequent English words (data/frequency_en.txt) take the translation table of
the word's best-covered meaning: it becomes a concept with the translations into our
languages. A meaning is used only if it has a Ukrainian translation (its Ukrainian name) and
covers enough of our languages.

Existing concepts are respected: if the English word already has a concept, the table is
merged into it only when its translations agree with that concept's words (otherwise the
word is skipped). Within a concept, a language that already has checked words (Wikidata
lexemes, editors, visitors, drafts) is left alone; only unverified fillers (concept labels,
machine words) are replaced by Wiktionary's translations.

    uv run python -m app.importers.wiktionary [--limit 5000]

The extract (~3.3 GB) is downloaded once to data/raw/wiktionary/. Re-runnable.
"""

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import httpx2
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.api.lexicon import UNVERIFIED_SOURCES
from app.db.session import SessionLocal
from app.importers.common import RAW_DIR, upsert_source
from app.importers.glosses import apply_glosses
from app.importers.languages import LANGUAGES
from app.models import PUBLIC_STATUSES, Audio, Concept, Form, Source, Variety
from app.slugs import assign_missing_slugs

DUMP_URL = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl"
DUMP_PATH = RAW_DIR / "wiktionary" / "kaikki-English.jsonl"
FREQUENCY_PATH = Path(__file__).parent / "data" / "frequency_en.txt"
# Words imported first whatever their frequency: the ones regional words need (apricot ->
# Marille, cauliflower -> Karfiol)
EXTRA_PATH = Path(__file__).parent / "data" / "extra_words_en.txt"

SOURCE_NAME = "Wiktionary translations"
# Croatian and Bosnian taken from Wiktionary's joint Serbo-Croatian table: its Latin forms
# may be Serbian (ekavian "rečnik" vs Croatian "rječnik"), so they are marked unverified.
SH_SOURCE_NAME = "Wiktionary translations (Serbo-Croatian, unverified)"
SOURCE_URL = "https://en.wiktionary.org/"
SOURCE_LICENSE = "CC BY-SA 4.0"
CATEGORY = "wiktionary"

POS = {"noun", "verb", "adj", "adv", "num", "intj"}  # intj: greetings ("hello", "goodbye")
MIN_LANGUAGES = 15  # translations into at least this many of our languages
MIN_AGREEMENT = 2  # same words in this many languages to merge into an existing concept
MAX_WORD_LENGTH = 60
MAX_VARIANTS = 3  # translations kept per language (the first is the main word)
COLLECT_VARIANTS = 10  # translations read per language before picking the most frequent

# Translations with these tags are left out (dialect, old, rare or rude words) ...
SKIP_TAGS = {
    "obsolete",
    "archaic",
    "dated",
    "rare",
    "uncommon",
    "humorous",
    "derogatory",
    "slang",
    "vulgar",
    "offensive",
    "pejorative",
    "euphemistic",
    "poetic",
    "figuratively",
    "idiomatic",
    "dialectal",
    "nonstandard",
    "Internet",
    "Alemannic-German",
    "Bavarian",
    "Low-German",
}
# ... and tags other than these grammar ones (colloquial, regional, country names) put a
# translation after the neutral ones, so the main word is the common one.
GRAMMAR_TAGS = {
    "masculine",
    "feminine",
    "neuter",
    "common",
    "plural",
    "singular",
    "imperfective",
    "perfective",
    "inanimate",
    "animate",
    "personal",
    "attributive",
    "with-dative",
    "with-genitive",
    "with-accusative",
    "with-instrumental",
    "before-vowel",
    "Cyrillic",
    "Roman",
    "Latin",
    "noun",
    "verb",
    "adjective",
}

# Wiktionary language code -> our variety code. Serbo-Croatian ("sh") is split by script.
WIKT_CODES = {lang.lemma_tag: lang.iso639_3 for lang in LANGUAGES}
WIKT_CODES["no"] = "nob"
CYRILLIC = re.compile(r"[Ѐ-ӿ]")

# Wiktionary marks stress, tone and vowel length that ordinary spelling leaves out
# ("словни́к", Serbo-Croatian "ре̑чнӣк", Latin "verbūm"). Combining marks removed per
# language; letters like й, ў, ё, Latvian ā or Lithuanian ū are left alone.
GRAVE, ACUTE, CIRCUMFLEX, TILDE, MACRON, BREVE = "̀", "́", "̂", "̃", "̄", "̆"
DOUBLE_GRAVE, INVERTED_BREVE = "̏", "̑"
STRESS_MARKS = {
    **dict.fromkeys(("ukr", "rus", "bel", "bul", "mkd"), {GRAVE, ACUTE}),
    **dict.fromkeys(("srp", "hrv", "bos"), {GRAVE, ACUTE, MACRON, DOUBLE_GRAVE, INVERTED_BREVE}),
    "slv": {GRAVE, ACUTE, CIRCUMFLEX, MACRON, DOUBLE_GRAVE, INVERTED_BREVE},
    "lit": {GRAVE, ACUTE, TILDE},
    "lat": {MACRON, BREVE},
    # Arabic short-vowel signs (harakat), which everyday writing leaves out
    "ara": {chr(c) for c in range(0x064B, 0x0653)} | {"ٰ"},
}


def plain_spelling(code: str, spelling: str) -> str:
    """The word without the stress/length marks of dictionaries: "словни́к" -> "словник"."""
    marks = STRESS_MARKS.get(code)
    if not marks:
        return spelling
    decomposed = unicodedata.normalize("NFD", spelling)
    return unicodedata.normalize("NFC", "".join(ch for ch in decomposed if ch not in marks))


# Translators' notes that sometimes end up in the word: "banować (on the internet)",
# "acordarse/arrecordarse", "jean (yin)"; a note saying the word is out of use drops it.
OUT_OF_USE = re.compile(r"\([^)]*\b(disused|desus|obsolete|archaic|dated|rare)\b", re.IGNORECASE)


def clean_translation(spelling: str) -> str | None:
    """The word without notes in brackets and alternatives after "/"; None if unusable."""
    if any(ch in spelling for ch in '"[]') or OUT_OF_USE.search(spelling):
        return None
    word = spelling.split("/")[0]
    word = re.sub(r"\([^()]*\)", "", word)  # "(voor) altijd", "saudade(s)", "발표(發表)하다"
    word = word.split(")")[-1].split("(")[0]  # what is left of unbalanced brackets
    word = re.sub(r"\s+", " ", word).strip(" ,;")
    return word or None


@dataclass
class Meaning:
    word: str
    sense: str
    # our variety code -> [(spelling, transliteration)]
    translations: dict[str, list[tuple[str, str | None]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # Croatian / Bosnian guessed from the Serbo-Croatian table (used if there is no direct one)
    from_serbo_croatian: dict[str, list[tuple[str, str | None]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # Colloquial / regional translations, added after the neutral ones if there is room
    later: dict[str, list[tuple[str, str | None]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def finish(self) -> None:
        """Order translations (most frequent neutral words first) and keep MAX_VARIANTS."""
        translations = {}
        for code in set(self.translations) | set(self.later):
            neutral = by_frequency(code, self.translations.get(code, []))
            spellings = neutral + [
                s for s in self.later.get(code, []) if s[0] not in (n for n, _ in neutral)
            ]
            if spellings:
                translations[code] = spellings[:MAX_VARIANTS]
        guessed = {}
        for code, spellings in self.from_serbo_croatian.items():
            if code not in translations and spellings:
                translations[code] = guessed[code] = by_frequency(code, spellings)[:MAX_VARIANTS]
        self.translations = translations
        self.from_serbo_croatian = guessed


try:  # optional (uv sync --group import): picks the common word among translations
    from wordfreq import available_languages, zipf_frequency

    FREQUENCY_LANGUAGES = set(available_languages())
except ImportError:  # keep Wiktionary's order
    zipf_frequency = None
    FREQUENCY_LANGUAGES = set()

# Our variety code -> wordfreq language
WORDFREQ_CODES = {lang.iso639_3: lang.lemma_tag for lang in LANGUAGES} | dict.fromkeys(
    ("srp", "hrv", "bos"), "sh"
)


# Zipf frequency below which a word counts as unknown to the frequency list
RARE = 1.0


def by_frequency(code: str, spellings: list[tuple[str, str | None]]) -> list:
    """Wiktionary's order, but words the frequency list doesn't know go last
    ("ogromny" before "gargantuiczny"). Common words are not promoted: they may be common
    in another meaning (Ukrainian "важкий" is listed for "pregnant", but means "heavy")."""
    language = WORDFREQ_CODES.get(code)
    if zipf_frequency is None or language not in FREQUENCY_LANGUAGES:
        return list(spellings)
    try:
        return sorted(spellings, key=lambda s: zipf_frequency(s[0], language) < RARE)
    except Exception:  # e.g. Japanese needs the MeCab tokenizer: keep Wiktionary's order
        FREQUENCY_LANGUAGES.discard(language)
        return list(spellings)


def download() -> Path:
    if not DUMP_PATH.exists():
        DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {DUMP_URL} (~3.3 GB) ...")
        with httpx2.stream("GET", DUMP_URL, follow_redirects=True, timeout=None) as response:
            response.raise_for_status()
            with DUMP_PATH.open("wb") as out:
                for chunk in response.iter_bytes(1 << 20):
                    out.write(chunk)
    return DUMP_PATH


def extra_words() -> list[str]:
    lines = EXTRA_PATH.read_text(encoding="utf-8").splitlines()
    return [w.split("#")[0].strip() for w in lines if w.strip() and not w.startswith("#")]


def frequent_words() -> list[str]:
    """The extra words, then the most frequent English words."""
    words: list[str] = []
    for path in (EXTRA_PATH, FREQUENCY_PATH):
        lines = path.read_text(encoding="utf-8").splitlines()
        words += [w.split("#")[0].strip() for w in lines if w.strip() and not w.startswith("#")]
    return list(dict.fromkeys(words))


def target_codes(item: dict) -> list[tuple[str, bool]]:
    """[(our variety code, guessed from Serbo-Croatian)]"""
    code = item.get("code") or item.get("lang_code")
    if code == "sh":
        if CYRILLIC.search(item.get("word", "")):
            return [("srp", False)]  # Cyrillic Serbo-Croatian is Serbian
        return [("hrv", True), ("bos", True)]
    return [(WIKT_CODES[code], False)] if code in WIKT_CODES else []


def read_meanings(path: Path, wanted: set[str]) -> tuple[dict[str, list[Meaning]], dict[str, str]]:
    """{English word: its translation tables}, {English word: IPA}."""
    meanings: dict[str, dict[str, Meaning]] = defaultdict(dict)
    ipa: dict[str, str] = {}
    with path.open(encoding="utf-8") as lines:
        for n, line in enumerate(lines, 1):
            if n % 200_000 == 0:
                print(f"  {n:,} entries read, {len(meanings):,} words with translations")
            if '"translations"' not in line:
                continue
            entry = json.loads(line)
            word = entry.get("word")
            if word not in wanted or entry.get("lang_code") != "en":
                continue
            if entry.get("pos") not in POS:
                continue
            for sound in entry.get("sounds", []):
                if "ipa" in sound and word not in ipa:
                    ipa[word] = sound["ipa"]
            # Translation tables sit on the entry or, more often, on its senses.
            items = list(entry.get("translations", []))
            for entry_sense in entry.get("senses", []):
                items.extend(entry_sense.get("translations", []))
            for item in items:
                sense = (item.get("sense") or "").strip()
                spelling = (item.get("word") or "").strip()
                if not sense or "to be checked" in sense.lower() or not spelling:
                    continue
                if len(spelling) > MAX_WORD_LENGTH:
                    continue
                key = f"{entry['pos']}: {sense}"
                meaning = meanings[word].setdefault(key, Meaning(word=word, sense=sense))
                tags = set(item.get("tags", []))
                if tags & SKIP_TAGS:
                    continue
                marked = bool(tags - GRAMMAR_TAGS)
                for code, guessed in target_codes(item):
                    table = (
                        meaning.from_serbo_croatian
                        if guessed
                        else meaning.later
                        if marked
                        else meaning.translations
                    )
                    known = table[code]
                    plain = clean_translation(plain_spelling(code, spelling))
                    if plain is None:
                        continue
                    if len(known) < COLLECT_VARIANTS and plain not in (s for s, _ in known):
                        known.append((plain, item.get("roman")))
    for by_sense in meanings.values():
        for meaning in by_sense.values():
            meaning.finish()
    return {w: list(m.values()) for w, m in meanings.items()}, ipa


def best_meaning(candidates: list[Meaning]) -> Meaning | None:
    usable = [m for m in candidates if "ukr" in m.translations]
    usable = [m for m in usable if len(m.translations) >= MIN_LANGUAGES]
    return max(usable, key=lambda m: len(m.translations), default=None)


def checked_words(session: Session, concept_id: int) -> dict[str, set[str]]:
    """{variety code: lower-case spellings} of a concept's public words."""
    rows = session.execute(
        select(Variety.code, Form.spelling)
        .join(Variety, Variety.id == Form.variety_id)
        .where(Form.concept_id == concept_id, Form.status.in_(PUBLIC_STATUSES))
    )
    words: dict[str, set[str]] = defaultdict(set)
    for code, spelling in rows:
        words[code].add(spelling.lower())
    return words


def agreement(meaning: Meaning, existing: dict[str, set[str]]) -> int:
    return sum(
        1
        for code, spellings in meaning.translations.items()
        if {s.lower() for s, _ in spellings} & existing.get(code, set())
    )


def save_meaning(
    session: Session,
    concept: Concept,
    meaning: Meaning,
    english_ipa: str | None,
    varieties: dict[str, Variety],
    source_id: int,
    sh_source_id: int,
    unverified_source_ids: set[int],
) -> int:
    """Add the translations to the concept; returns the number of new words."""
    translations = dict(meaning.translations)
    translations.setdefault("eng", [(meaning.word, None)])
    added = 0
    for code, spellings in translations.items():
        variety = varieties.get(code)
        if variety is None:
            continue
        forms = session.scalars(
            select(Form).where(Form.concept_id == concept.id, Form.variety_id == variety.id)
        ).all()
        own_sources = {source_id, sh_source_id}
        form_source = sh_source_id if code in meaning.from_serbo_croatian else source_id
        has_checked = any(
            f.source_id not in unverified_source_ids and f.source_id not in own_sources
            for f in forms
        )
        if has_checked:
            continue  # real data wins
        # Unverified fillers (labels, machine words) give way to Wiktionary's translations.
        for form in forms:
            if form.source_id in unverified_source_ids and form.source_id not in own_sources:
                session.delete(form)
        session.flush()
        ours = {f.spelling: f for f in forms if f.source_id in own_sources}
        for i, (spelling, roman) in enumerate(spellings):
            form = ours.pop(spelling, None)
            if form is None:
                form = Form(concept=concept, variety=variety, spelling=spelling)
                session.add(form)
                added += 1
            form.source_id = form_source
            form.is_primary = i == 0
            form.status = "approved"
            form.transliteration = roman
            if code == "eng" and english_ipa:
                form.ipa = english_ipa
        for stale in ours.values():
            session.delete(stale)
    return added


def clean_existing(session: Session) -> None:
    """Apply clean_translation to words imported before it existed: fix their spelling, or
    drop them when unusable or when the concept already has the clean word."""
    sources = [s.id for s in session.scalars(select(Source).where(Source.name.like("Wiktionary%")))]
    forms = list(session.scalars(select(Form).where(Form.source_id.in_(sources))))
    spellings = {(f.concept_id, f.variety_id, f.spelling) for f in forms}
    fixed = dropped = 0
    for form in forms:
        clean = clean_translation(form.spelling)
        if clean == form.spelling:
            continue
        # Synthetic audio was made from the old text
        session.execute(delete(Audio).where(Audio.form_id == form.id, Audio.is_synthetic))
        if clean is None or (form.concept_id, form.variety_id, clean) in spellings:
            session.delete(form)
            dropped += 1
        else:
            form.spelling = clean
            spellings.add((form.concept_id, form.variety_id, clean))
            fixed += 1
    session.flush()
    # A dropped main word: the next word of that language becomes the main one
    session.execute(
        text("""
            UPDATE form f SET is_primary = true
            WHERE f.id IN (
                SELECT DISTINCT ON (concept_id, variety_id) id FROM form g
                WHERE NOT EXISTS (SELECT 1 FROM form p WHERE p.concept_id = g.concept_id
                                  AND p.variety_id = g.variety_id AND p.is_primary)
                ORDER BY concept_id, variety_id, id)
        """)
    )
    session.commit()
    print(f"Cleaned earlier words: {fixed} fixed, {dropped} dropped.")


def main(limit: int) -> None:
    words = frequent_words()
    limit += len(extra_words())
    print(f"Reading {DUMP_PATH.name} for {len(words):,} frequent English words ...")
    meanings, ipa = read_meanings(download(), set(words))

    with SessionLocal() as session:
        clean_existing(session)
        source = upsert_source(session, SOURCE_NAME, SOURCE_URL, SOURCE_LICENSE)
        sh_source = upsert_source(session, SH_SOURCE_NAME, SOURCE_URL, SOURCE_LICENSE)
        unverified_ids = set(
            session.scalars(select(Source.id).where(Source.name.in_(UNVERIFIED_SOURCES)))
        )
        varieties = {v.code: v for v in session.scalars(select(Variety))}

        # Existing concepts by their English name (without a "(hint)") and English words.
        by_english: dict[str, set[Concept]] = defaultdict(set)
        existing = session.scalars(select(Concept).where(Concept.category != CATEGORY)).all()
        for concept in existing:
            by_english[re.sub(r"\s*\(.*\)$", "", concept.gloss_en).lower()].add(concept)
        english_forms = session.execute(
            select(Form.concept_id, Form.spelling)
            .join(Variety, Variety.id == Form.variety_id)
            .where(Variety.code == "eng", Form.status.in_(PUBLIC_STATUSES))
        )
        by_id = {c.id: c for c in existing}
        for concept_id, spelling in english_forms:
            if concept_id in by_id:
                by_english[spelling.lower()].add(by_id[concept_id])
        used_uk_names = {c.gloss_uk for c in session.scalars(select(Concept)) if c.gloss_uk}
        ours = {
            c.gloss_en: c
            for c in session.scalars(select(Concept).where(Concept.category == CATEGORY))
        }

        done = merged = skipped = added_words = 0
        for word in words:
            if done >= limit:
                break
            meaning = best_meaning(meanings.get(word, []))
            if meaning is None:
                continue
            concept = ours.get(word)
            if concept is None and word in by_english:
                # The word already has a concept: merge only if the translations agree.
                scored = [
                    (agreement(meaning, checked_words(session, c.id)), c) for c in by_english[word]
                ]
                score, best = max(scored, key=lambda s: s[0])
                if score < MIN_AGREEMENT:
                    skipped += 1
                    continue
                concept = best
                merged += 1
            if concept is None or concept.category == CATEGORY:
                # Our own concept: its name and description follow the chosen meaning.
                if concept is not None:
                    used_uk_names.discard(concept.gloss_uk)
                uk_name = meaning.translations["ukr"][0][0]
                if uk_name in used_uk_names:
                    # Another concept has this Ukrainian name ("великий" for big and large).
                    uk_name = f"{uk_name} ({word})"
                used_uk_names.add(uk_name)
                if concept is None:
                    concept = Concept(gloss_en=word, category=CATEGORY)
                    session.add(concept)
                concept.gloss_uk = uk_name
                apply_glosses(concept)  # our fixed names win ("цвітна капуста")
                concept.description_en = meaning.sense[:500]
                session.flush()
                ours[word] = concept
            added_words += save_meaning(
                session,
                concept,
                meaning,
                ipa.get(word),
                varieties,
                source.id,
                sh_source.id,
                unverified_ids,
            )
            done += 1
            if done % 500 == 0:
                session.commit()
                print(f"  {done:,} concepts ({merged} merged into existing, {skipped} skipped)")
        slugs = assign_missing_slugs(session)
        session.commit()
    print(
        f"Done: {done:,} concepts ({merged} merged into existing ones, {skipped} skipped as "
        f"a different meaning), {added_words:,} new words, {slugs} new slugs."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--limit", type=int, default=5000, help="frequent concepts to import (plus the extra words)"
    )
    main(parser.parse_args().limit)
