"""Regional words from Hrinchenko's "Словарь української мови" (1907–1909; Berlin reprint 1924,
transcribed and proofread on uk.wikisource, public domain text).

Each entry cites where the word was recorded: collections such as Shukhevych's "Гуцульщина"
("Шух.") or place labels such as "Волин.". Entries recorded only in one dialect's area become
words of that dialect. The dictionary explains words in (pre-1918) Russian, so the entry is
tied to a concept through our Russian words ("Грачъ" → грач → rook). To keep mistakes few,
only entries with one meaning given as synonyms ("Пылкій, страстный") are used, and words
common in today's Ukrainian (wordfreq) are skipped as standard.

    uv run --group import python -m app.importers.grinchenko             # import as drafts
    uv run --group import python -m app.importers.grinchenko --sample N  # print N, no changes

Words become drafts ("pending", shown with "≈") of the dialect, checked by visitors and
editors; the printed entry (with stress marks) is kept in the form's note. Re-runnable:
drafts from this source are replaced, approved ones are kept. Pages are downloaded once to
data/raw/grinchenko/pages.jsonl (~20 MB).
"""

import argparse
import json
import random
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import httpx2
from sqlalchemy import delete, select, text

from app.db.session import SessionLocal
from app.importers.common import RAW_DIR, upsert_source
from app.models import PENDING, Form, Variety

API_URL = "https://uk.wikisource.org/w/api.php"
PAGE_PREFIX = "Грінченко. Словарь української мови (1924). Том {volume}.djvu/"
PAGES_PATH = RAW_DIR / "grinchenko" / "pages.jsonl"
USER_AGENT = "DialectioBot/0.1 (https://github.com/gmisha777/dialectio)"

SOURCE_NAME = "Словарь української мови Б. Грінченка (1907–1909), Вікіджерела"
SOURCE_URL = "https://uk.wikisource.org/wiki/Словарь_української_мови_(1924)"
SOURCE_LICENSE = "Public domain (text); CC BY-SA 4.0 (Wikisource transcription)"

# Collections recorded in one dialect's area (abbreviations from the dictionary's list of
# sources) and place labels; longest first so "Вх. Лем." wins over shorter ones.
SOURCE_DIALECTS = {
    "Шух.": "ukr-hutsul",  # Шухевич, Гуцульщина
    "Вх. Лем.": "ukr-lemko",  # Верхратський, Про говір галицьких лемків
    "Вх. Уг.": "ukr-transcarpathian",  # Верхратський, угорсько-руські говори
    "Угор.": "ukr-transcarpathian",  # Угорська Русь
    "Буков.": "ukr-pokuttia-bukovyna",
    "Волин.": "ukr-volhynian",
    "Ровен.": "ukr-volhynian",
    "Подол.": "ukr-podillian",
    "Брацл.": "ukr-podillian",
    "Харьк.": "ukr-slobozhan",
    "Лебед.": "ukr-slobozhan",
    "Зміев.": "ukr-slobozhan",
    "Сумск.": "ukr-slobozhan",
    "Херс.": "ukr-steppe",
    "Катер.": "ukr-steppe",
    "Новомоск.": "ukr-steppe",
    "Полт.": "ukr-middle-dnieper",
    "Черк.": "ukr-middle-dnieper",
    "Канев.": "ukr-middle-dnieper",
    "Лохв.": "ukr-middle-dnieper",
    "Мирг.": "ukr-middle-dnieper",
    "Пирят.": "ukr-middle-dnieper",
    "Прилук.": "ukr-middle-dnieper",
    "Гадяч.": "ukr-middle-dnieper",
    "Звенигор.": "ukr-middle-dnieper",
    "Черниг.": "ukr-polissia-east",
    "Борз.": "ukr-polissia-east",
    "Конотоп.": "ukr-polissia-east",
    "Сосниц.": "ukr-polissia-east",
    "Радомысл.": "ukr-polissia-central",
}
LABEL = re.compile(
    r"(?<![\w'])("
    + "|".join(re.escape(a) for a in sorted(SOURCE_DIALECTS, key=len, reverse=True))
    + ")"
)
# Any place label: "Черниг. у." (district), "Харьк. г." (province)
PLACE = re.compile(r"(?<![\w'])([А-ЯІЇЄҐ][а-яіїєґ]+\.)\s[уг]\.")
# Any citation: "Шевч. 411", "Ном. № 705", "Рудч. Ск. I. 125"
CITATION = re.compile(
    r"(?<![\w'])([А-ЯІЇЄҐ][а-яіїєґ']{0,7}\.)(?:\s[А-ЯІЇЄҐ][а-яіїєґ']*\.)?"
    r"\s*(?:[IVX]+\.\s*)?(?:№\s*)?\d"
)
# A definition that is a list of synonyms ("Пылкій, страстный"), not a description
SYNONYMS = re.compile(r"[а-яёѣіѳѵъ-]+(\s*,\s*[а-яёѣіѳѵъ-]+)*", re.IGNORECASE)
# Words this frequent in today's Ukrainian (wordfreq Zipf scale) are standard, not dialect
STANDARD_ZIPF = 2.0

SECTION = re.compile(r'<section begin="([^"]+)"\s*/>(.*?)<section end="\1"\s*/>', re.S)
BOLD = re.compile(r"'''(.+?)'''")
ITALIC = re.compile(r"''.*?''")
LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
STRESS = "́"
# Pre-1918 Russian spelling → modern, enough to compare words ("лѣсъ" → "лес")
OLD_RUSSIAN = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и"})
GRAMMAR = re.compile(r"^(м|ж|с|гл|нар|прил|меж|мн|соб|сущ|числ|мест|предл|союз|ум|ув)\.?$")


@dataclass
class Entry:
    section: str  # the entry's name on Wikisource
    word: str  # with stress marks, as printed ("Гайбу́з")
    meanings: list[str]  # the Russian word explaining it, modern spelling
    dialects: set[str] = field(default_factory=set)
    other_sources: bool = False  # also cited from sources not tied to one area
    text: str = ""

    @property
    def plain(self) -> str:
        return unicodedata.normalize("NFC", self.word.replace(STRESS, "")).lower()


def download() -> Path:
    if PAGES_PATH.exists():
        return PAGES_PATH
    PAGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    with httpx2.Client(headers={"User-Agent": USER_AGENT}, timeout=60) as client:
        for volume in (1, 2):
            params = {
                "action": "query",
                "format": "json",
                "generator": "allpages",
                "gapnamespace": 250,  # Сторінка: the transcribed scan pages
                "gapprefix": PAGE_PREFIX.format(volume=volume),
                "gaplimit": 50,
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
            }
            while True:
                data = client.get(API_URL, params=params).raise_for_status().json()
                for page in data.get("query", {}).get("pages", {}).values():
                    content = page.get("revisions", [{}])[0].get("slots", {}).get("main", {})
                    number = int(page["title"].rsplit("/", 1)[1])
                    lines.append({"volume": volume, "page": number, "text": content.get("*", "")})
                if "continue" not in data:
                    break
                params.update(data["continue"])
                time.sleep(0.5)
    PAGES_PATH.write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines), encoding="utf-8"
    )
    return PAGES_PATH


def sections() -> dict[str, str]:
    """{section name: entry text}, an entry continued on the next page joined."""
    pages = [json.loads(line) for line in download().open(encoding="utf-8")]
    pages.sort(key=lambda p: (p["volume"], p["page"]))
    found: dict[str, str] = {}
    for page in pages:
        for name, body in SECTION.findall(page["text"]):
            found[name] = f"{found[name]} {body}" if name in found else body
    return found


def first_word(definition: str) -> str | None:
    """'Роща, небольшой лѣсъ' → 'роща'; None for a phrase ('Свойственный грачу')."""
    head = re.split(r"[,;.:(]", definition, maxsplit=1)[0].strip().lower()
    head = re.sub(r"ъ\b", "", head.translate(OLD_RUSSIAN))
    return head if re.fullmatch(r"[а-яё-]{2,}", head) else None


def parse(section: str, body: str) -> Entry | None:
    body = LINK.sub(r"\1", body).replace("\xa0", " ")
    header = BOLD.search(body)
    if not header:
        return None
    word = re.sub(r"^[IVX]+\.\s*", "", header.group(1)).split(",")[0].strip(" !.")
    rest = ITALIC.sub(" ", body[header.end() :])  # italics: grammar and examples
    if not word or " " in word or rest.lstrip(" ,.").startswith("="):
        return None  # phrases and cross-references ("= Гав'яр")
    meanings = []
    if not re.search(r"\d\)", rest):  # one meaning only: several are ambiguous
        definition = re.sub(r"^[\s,.]*", "", rest).split(".")[0].strip()
        meaning = first_word(definition)
        if meaning and not GRAMMAR.match(meaning) and SYNONYMS.fullmatch(definition):
            meanings.append(meaning)
    labels = set(LABEL.findall(body))
    unknown_places = {p for p in PLACE.findall(body) if p not in SOURCE_DIALECTS}
    citations = CITATION.findall(body)
    other = bool(unknown_places) or any(not LABEL.fullmatch(c) for c in citations if c != "Вх.")
    return Entry(
        section=section,
        word=unicodedata.normalize("NFC", word),
        meanings=meanings,
        dialects={SOURCE_DIALECTS[label] for label in labels},
        other_sources=other,
        text=body,
    )


RUSSIAN_CONCEPTS = text("""
    SELECT lower(f.spelling) AS word, array_agg(DISTINCT f.concept_id) AS concepts
    FROM form f JOIN variety v ON v.id = f.variety_id
    WHERE v.code = 'rus' AND f.status IN ('approved', 'pending')
    GROUP BY 1
""")
# Ukrainian words we already have (our own earlier drafts don't count: they are replaced)
UKRAINIAN_WORDS = text("""
    SELECT f.concept_id, lower(f.spelling)
    FROM form f JOIN variety v ON v.id = f.variety_id
    LEFT JOIN source s ON s.id = f.source_id
    WHERE (v.code = 'ukr' OR v.code LIKE 'ukr-%') AND f.status IN ('approved', 'pending')
      AND (s.name IS DISTINCT FROM :source OR f.status = 'approved')
""")
CONCEPT_NAMES = text("SELECT id, gloss_uk, gloss_en FROM concept")


def candidates() -> list[tuple[Entry, int]]:
    """(entry, concept id) for words recorded in one dialect's area only."""
    from wordfreq import zipf_frequency  # optional dependency (uv run --group import)

    with SessionLocal() as session:
        russian = {w: c for w, c in session.execute(RUSSIAN_CONCEPTS)}
        ukrainian: dict[int, set[str]] = defaultdict(set)
        for concept_id, spelling in session.execute(UKRAINIAN_WORDS, {"source": SOURCE_NAME}):
            ukrainian[concept_id].add(spelling)
    found = []
    for section, body in sections().items():
        entry = parse(section, body)
        if not entry or len(entry.dialects) != 1 or entry.other_sources or not entry.meanings:
            continue
        concepts = russian.get(entry.meanings[0], [])
        if len(concepts) != 1 or entry.plain in ukrainian[concepts[0]]:
            continue
        if zipf_frequency(entry.plain, "uk") >= STANDARD_ZIPF:
            continue
        found.append((entry, concepts[0]))
    return found


def note(entry: Entry) -> str:
    """The entry as printed, for editors: 'Грінченко: Верста́к, ка́, м. Ровесникъ. Шух. I. 32'."""
    plain = re.sub(r"\s+", " ", re.sub(r"'{2,3}", "", entry.text)).strip()
    return f"Грінченко: {plain}"[:1000]


def sample(size: int) -> None:
    found = candidates()
    by_dialect: dict[str, int] = defaultdict(int)
    for entry, _ in found:
        by_dialect[next(iter(entry.dialects))] += 1
    print(f"{len(found)} candidates:", dict(sorted(by_dialect.items(), key=lambda x: -x[1])))
    with SessionLocal() as session:
        names = {i: (uk or en) for i, uk, en in session.execute(CONCEPT_NAMES)}
    random.seed(7)
    for entry, concept_id in random.sample(found, min(size, len(found))):
        dialect = next(iter(entry.dialects))
        print(f"{entry.word:<16} {dialect:<22} → {names[concept_id]:<14} | {note(entry)[:110]}")


def load() -> None:
    found = candidates()
    with SessionLocal() as session:
        source = upsert_source(session, SOURCE_NAME, SOURCE_URL, SOURCE_LICENSE)
        session.execute(delete(Form).where(Form.source_id == source.id, Form.status == PENDING))
        varieties = {v.code: v for v in session.scalars(select(Variety))}
        existing = set()
        has_primary = set()
        for concept_id, variety_id, spelling, is_primary in session.execute(
            select(Form.concept_id, Form.variety_id, Form.spelling, Form.is_primary)
        ):
            existing.add((concept_id, variety_id, spelling.lower()))
            if is_primary:
                has_primary.add((concept_id, variety_id))
        added = 0
        for entry, concept_id in found:
            variety = varieties[next(iter(entry.dialects))]
            if (concept_id, variety.id, entry.plain) in existing:
                continue
            primary = (concept_id, variety.id) not in has_primary
            session.add(
                Form(
                    concept_id=concept_id,
                    variety=variety,
                    spelling=entry.plain,
                    is_primary=primary,
                    status=PENDING,
                    source=source,
                    external_id=entry.section[:50],
                    note=note(entry),
                )
            )
            existing.add((concept_id, variety.id, entry.plain))
            has_primary.add((concept_id, variety.id))
            added += 1
        session.commit()
    print(f"Added {added} dialect drafts from Hrinchenko's dictionary.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, help="only print N random candidates")
    args = parser.parse_args()
    if args.sample:
        sample(args.sample)
    else:
        load()
