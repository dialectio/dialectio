"""Word families: which translations of a concept look related (patata / batata / potato vs
Kartoffel / kartof / картопля), for colouring the map by the word's origin.

This is a rough, automatic grouping by similar spelling in Latin script (transliterations for
other scripts), not etymology from a dictionary: words borrowed from a common source usually
stay similar, unrelated words usually don't.
"""

import unicodedata
from difflib import SequenceMatcher

from app.romanize import OTHER_CYRILLIC, UKRAINIAN

# Two words are related if their Latin forms are this similar (0..1) ...
SIMILARITY = 0.6
# ... stricter for short words, which look alike by chance ("nan" / "pan")
SHORT = 4
SHORT_SIMILARITY = 0.75
# ... or start with the same letters (Kartoffel / kartof)
SAME_START = 4
MIN_LENGTH = 2
LATIN_LETTER = "abcdefghijklmnopqrstuvwxyz"
# Letters whose sound is lost when the accent is dropped (Turkish "çay", Czech "čaj" = "chai")
LATIN_SOUNDS = {
    "č": "ch",
    "ç": "ch",
    "ć": "ch",
    "š": "sh",
    "ş": "sh",
    "ś": "sh",
    "ž": "zh",
    "ź": "zh",
    "ż": "zh",
}


def latin_form(code: str, spelling: str, transliteration: str | None) -> str | None:
    """The word in plain Latin letters, or None if it can't be compared."""
    word = spelling.lower()
    if any("Ѐ" <= ch <= "ӿ" for ch in word):
        table = UKRAINIAN if code.startswith("ukr") else OTHER_CYRILLIC
        word = "".join(table.get(ch, ch) for ch in word)
    elif transliteration and not all(ch.isascii() for ch in word if ch.isalpha()):
        word = transliteration.lower()
    for letter, sound in LATIN_SOUNDS.items():
        word = word.replace(letter, sound)
    word = unicodedata.normalize("NFKD", word)
    word = "".join(ch for ch in word if ch in LATIN_LETTER)
    return word if len(word) >= MIN_LENGTH else None


def related(a: str, b: str) -> bool:
    if a[:SAME_START] == b[:SAME_START] and len(a) >= SAME_START and len(b) >= SAME_START:
        return True
    threshold = SHORT_SIMILARITY if min(len(a), len(b)) <= SHORT else SIMILARITY
    return SequenceMatcher(None, a, b).ratio() >= threshold


def word_families(words: dict[str, str]) -> dict[str, int]:
    """{language code: Latin word} -> {language code: family}, families numbered from 0 by
    size (largest first). Languages whose word has no relative get no family."""
    codes = list(words)
    parent = {code: code for code in codes}

    def root(code: str) -> str:
        while parent[code] != code:
            parent[code] = parent[parent[code]]
            code = parent[code]
        return code

    for i, a in enumerate(codes):
        for b in codes[i + 1 :]:
            if related(words[a], words[b]):
                parent[root(a)] = root(b)

    groups: dict[str, list[str]] = {}
    for code in codes:
        groups.setdefault(root(code), []).append(code)
    families = sorted((g for g in groups.values() if len(g) > 1), key=len, reverse=True)
    return {code: number for number, group in enumerate(families) for code in group}
