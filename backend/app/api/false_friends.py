"""False friends: words that look or sound like a Ukrainian word but mean something else
(Polish "dywan" is a carpet, Ukrainian "диван" a sofa).

Pairs are found among the main words of our concepts: both words are reduced to a rough
sound key in Latin script (per-language rules: Polish "w" = "v", "sz" = "sh"; Russian "и" =
Ukrainian "і"; vowels e/i/y merged), and a pair counts when the keys match but the concepts
differ and neither word is a translation of the other's concept.
"""

import time
import unicodedata
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.api.lexicon import SessionDep
from app.romanize import OTHER_CYRILLIC, UKRAINIAN

router = APIRouter(prefix="/api/false-friends", tags=["false friends"])

# Languages with false-friend pages (closely related ones, where they are common)
LANGUAGES = ("pol", "rus", "bel", "slk", "ces", "bul", "srp", "hrv")
MIN_LENGTH = 3  # letters in the key: shorter words match by chance
MAX_PAIRS = 200
CACHE_SECONDS = 3600

# Latin alphabets: letters and digraphs spelled for the same sound as the Ukrainian romanization
LATIN = {
    "pol": [
        ("ch", "kh"),
        ("cz", "ch"),
        ("sz", "sh"),
        ("rz", "zh"),
        ("ż", "zh"),
        ("ź", "zh"),
        ("ś", "sh"),
        ("ć", "ch"),
        ("ł", "l"),
        ("w", "v"),
        ("ą", "on"),
        ("ę", "en"),
        ("ó", "u"),
        ("ń", "n"),
    ],
    "ces": [("ch", "kh"), ("č", "ch"), ("š", "sh"), ("ž", "zh"), ("ř", "rzh"), ("w", "v")],
    "slk": [("ch", "kh"), ("č", "ch"), ("š", "sh"), ("ž", "zh"), ("ä", "e"), ("w", "v")],
    "hrv": [
        ("č", "ch"),
        ("ć", "ch"),
        ("š", "sh"),
        ("ž", "zh"),
        ("đ", "dzh"),
        ("dž", "dzh"),
        ("lj", "l"),
        ("nj", "n"),
        ("j", "i"),
    ],
}


def sound_key(code: str, word: str) -> str:
    """A rough Latin "sound" of the word: "dywan" (pol) and "диван" (ukr) -> "divan"."""
    word = word.lower()
    if code == "ukr":
        key = "".join(UKRAINIAN.get(ch, ch) for ch in word)
    elif code in LATIN:
        key = word
        for spelled, sound in LATIN[code]:
            key = key.replace(spelled, sound)
    else:
        key = "".join(OTHER_CYRILLIC.get(ch, ch) for ch in word)
    key = unicodedata.normalize("NFKD", key)
    key = "".join(ch for ch in key if ch.isalpha() and not unicodedata.combining(ch))
    # Vowels that swap between related languages (неділя / неделя) count as one
    return key.translate(str.maketrans({"e": "i", "y": "i"}))


class Word(BaseModel):
    spelling: str
    slug: str
    gloss_en: str
    gloss_uk: str | None
    glosses: dict[str, str] = {}
    # The concept's word in the other language (what "диван" really is in Polish: "kanapa")
    translation: str | None


class FalseFriend(BaseModel):
    foreign: Word  # e.g. Polish "dywan" (concept "carpet")
    ukrainian: Word  # e.g. Ukrainian "диван" (concept "sofa")


class LanguagePairs(BaseModel):
    code: str
    name_en: str
    name_uk: str | None
    names: dict[str, str] = {}
    pairs: list[FalseFriend]


class LanguageCount(BaseModel):
    code: str
    name_en: str
    name_uk: str | None
    names: dict[str, str] = {}
    count: int


# Every public word (not only the main ones), to recognise synonyms and shared meanings
ALL_WORDS = text("""
    SELECT f.concept_id, f.spelling
    FROM form f JOIN variety v ON v.id = f.variety_id AND v.code = :code
    WHERE f.status IN ('approved', 'pending')
""")

PRIMARY_WORDS = text("""
    SELECT f.concept_id, f.spelling, c.slug, c.gloss_en, c.gloss_uk, c.glosses
    FROM form f
    JOIN variety v ON v.id = f.variety_id AND v.code = :code
    JOIN concept c ON c.id = f.concept_id AND c.slug IS NOT NULL
    WHERE f.is_primary AND f.status IN ('approved', 'pending')
    ORDER BY f.concept_id
""")


@dataclass
class Entry:
    concept_id: int
    spelling: str
    slug: str
    gloss_en: str
    gloss_uk: str | None
    glosses: dict[str, str]


_cache: dict[str, tuple[float, list[FalseFriend]]] = {}


def words(session: SessionDep, code: str) -> list[Entry]:
    return [Entry(**row) for row in session.execute(PRIMARY_WORDS, {"code": code}).mappings()]


def find_pairs(session: SessionDep, code: str) -> list[FalseFriend]:
    cached = _cache.get(code)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    ukrainian = words(session, "ukr")
    foreign = words(session, code)
    ukr_by_concept = {w.concept_id: w for w in ukrainian}
    foreign_by_concept = {w.concept_id: w for w in foreign}
    # {concept: sound keys of all its words}, in Ukrainian and in the other language
    all_keys: dict[str, dict[int, set[str]]] = {}
    for lang in ("ukr", code):
        keys = all_keys.setdefault(lang, {})
        for concept_id, spelling in session.execute(ALL_WORDS, {"code": lang}):
            keys.setdefault(concept_id, set()).add(sound_key(lang, spelling))
    ukr_keys: dict[str, list[Entry]] = {}
    for w in ukrainian:
        key = sound_key("ukr", w.spelling)
        if len(key) >= MIN_LENGTH:
            ukr_keys.setdefault(key, []).append(w)

    ranked: list[tuple[int, FalseFriend]] = []
    seen: set[tuple[str, str]] = set()
    for f in foreign:
        for u in ukr_keys.get(sound_key(code, f.spelling), []):
            pair_words = (f.spelling.lower(), u.spelling.lower())
            if u.concept_id == f.concept_id or pair_words in seen:
                continue
            key = sound_key(code, f.spelling)
            # No false friend if the words share a meaning after all: the foreign word also
            # names the Ukrainian word's concept, or Ukrainian uses this word for both concepts
            # ("рука" for arm and hand).
            if key in all_keys[code].get(u.concept_id, set()):
                continue
            if key in all_keys["ukr"].get(f.concept_id, set()):
                continue
            own_word = foreign_by_concept.get(u.concept_id)
            seen.add(pair_words)  # the same two words once, even if they name several concepts
            ukr_meaning = ukr_by_concept.get(f.concept_id)
            # Concepts imported earlier are the core and most frequent words: they go first.
            rank = f.concept_id + u.concept_id
            ranked.append(
                (
                    rank,
                    FalseFriend(
                        foreign=Word(
                            spelling=f.spelling,
                            slug=f.slug,
                            gloss_en=f.gloss_en,
                            gloss_uk=f.gloss_uk,
                            glosses=f.glosses,
                            translation=ukr_meaning.spelling if ukr_meaning else None,
                        ),
                        ukrainian=Word(
                            spelling=u.spelling,
                            slug=u.slug,
                            gloss_en=u.gloss_en,
                            gloss_uk=u.gloss_uk,
                            glosses=u.glosses,
                            translation=own_word.spelling if own_word else None,
                        ),
                    ),
                )
            )
    ranked.sort(key=lambda r: r[0])
    pairs = [pair for _, pair in ranked[:MAX_PAIRS]]
    _cache[code] = (time.monotonic(), pairs)
    return pairs


def language(session: SessionDep, code: str):
    return (
        session.execute(
            text("SELECT code, name_en, name_uk, names FROM variety WHERE code = :code"),
            {"code": code},
        )
        .mappings()
        .first()
    )


@router.get("")
def list_languages(session: SessionDep) -> list[LanguageCount]:
    return [
        LanguageCount(**language(session, code), count=len(find_pairs(session, code)))
        for code in LANGUAGES
    ]


@router.get("/{code}")
def false_friends(session: SessionDep, code: str) -> LanguagePairs:
    if code not in LANGUAGES:
        raise HTTPException(status_code=404, detail="No false friends for this language")
    return LanguagePairs(**language(session, code), pairs=find_pairs(session, code))
