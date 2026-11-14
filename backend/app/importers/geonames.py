"""Import settlements (cities, towns, villages) from GeoNames into `settlement`.

They answer "where do they say it?" when a member adds a word: a search by name in any
language and "my location" (the nearest settlement). Countries with oblasts on our map get
every settlement GeoNames has, with names in our interface languages; the rest of the world
gets towns of 1 000+ people. Each settlement is tied to the oblast (else the country) it lies in.

Run from backend/ after the region importers:  uv run python -m app.importers.geonames
(~150 MB download to data/raw/geonames/, a few minutes; re-runnable)
"""

import csv
import io
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path

import httpx2
from sqlalchemy import text

from app.db.session import SessionLocal
from app.importers.common import RAW_DIR, upsert_source
from app.importers.natural_earth_admin1 import COUNTRIES

BASE_URL = "https://download.geonames.org/export/dump"
SOURCE_NAME = "GeoNames"
SOURCE_URL = "https://www.geonames.org/"
SOURCE_LICENSE = "CC BY 4.0"
DOWNLOAD_DIR = RAW_DIR / "geonames"

# Every settlement for the countries with oblasts on our map, big towns elsewhere
FULL_COUNTRIES = sorted(COUNTRIES)
WORLD_FILE = "cities1000"
# Not real settlements: historical, abandoned, destroyed, sections of a city, religious sites
SKIP_CODES = {"PPLH", "PPLQ", "PPLW", "PPLX", "PPLCH"}
# Names kept per language: the interface languages and the local ones of FULL_COUNTRIES
NAME_LANGUAGES = {"uk", "en", "pl", "de", "es", "fr", "sk", "ro", "nl", "it"}

csv.field_size_limit(2**31 - 1)  # a C long on Windows too

LOAD = text("""
    INSERT INTO settlement (id, name, names, keys, country, population, geom, source_id)
    SELECT id, name, names, keys, country, population,
           ST_SetSRID(ST_MakePoint(lon, lat), 4326), :source_id
    FROM settlement_load
    ON CONFLICT (id) DO UPDATE
    SET name = EXCLUDED.name, names = EXCLUDED.names, keys = EXCLUDED.keys,
        country = EXCLUDED.country, population = EXCLUDED.population, geom = EXCLUDED.geom,
        source_id = EXCLUDED.source_id
""")

# The oblast a settlement lies in, else its country; settlements on a coast just outside the
# simplified borders get the nearest region within ~10 km.
ASSIGN_REGIONS = [
    text("UPDATE settlement SET region_id = NULL"),
    text("""
        UPDATE settlement s SET region_id = r.id
        FROM region r
        WHERE r.level = 'adm1' AND ST_Intersects(r.geom, s.geom)
    """),
    text("""
        UPDATE settlement s SET region_id = r.id
        FROM region r
        WHERE s.region_id IS NULL AND r.level = 'country' AND ST_Intersects(r.geom, s.geom)
    """),
    text("""
        UPDATE settlement s SET region_id = (
            SELECT r.id FROM region r
            WHERE ST_DWithin(r.geom, s.geom, 0.1)
            ORDER BY r.level = 'country', r.geom <-> s.geom
            LIMIT 1)
        WHERE s.region_id IS NULL
    """),
]


def download(name: str, folder: str = "") -> Path:
    target = DOWNLOAD_DIR / (f"alt-{name}.zip" if folder else f"{name}.zip")
    if not target.exists():
        url = f"{BASE_URL}/{folder + '/' if folder else ''}{name}.zip"
        print("downloading", url)
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        with httpx2.stream("GET", url, follow_redirects=True, timeout=600) as response:
            response.raise_for_status()
            with target.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
    return target


def rows(path: Path, member: str) -> Iterator[list[str]]:
    with zipfile.ZipFile(path) as archive, archive.open(member) as raw:
        reader = csv.reader(
            io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE
        )
        yield from reader


def local_names(country: str, ids: set[int]) -> dict[int, dict[str, str]]:
    """{geonameid: {language: name}}: the preferred name in each language, else the first one
    that is neither historic nor colloquial."""
    names: dict[int, dict[str, str]] = {}
    preferred: set[tuple[int, str]] = set()
    for row in rows(download(country, "alternatenames"), f"{country}.txt"):
        geoname_id, language, name = int(row[1]), row[2], row[3]
        if geoname_id not in ids or language not in NAME_LANGUAGES:
            continue
        is_preferred, is_colloquial, is_historic = row[4] == "1", row[6] == "1", row[7] == "1"
        if is_historic or is_colloquial:
            continue
        own = names.setdefault(geoname_id, {})
        if is_preferred and (geoname_id, language) not in preferred:
            own[language] = name
            preferred.add((geoname_id, language))
        else:
            own.setdefault(language, name)
    return names


CYRILLIC = re.compile(r"[а-яёіїєґ]", re.IGNORECASE)
UKRAINIAN_LETTERS = re.compile(r"[іїєґ]", re.IGNORECASE)
RUSSIAN_LETTERS = re.compile(r"[ыэёъ]", re.IGNORECASE)


def fix_ukrainian(own: dict[str, str], alternates: list[str]) -> None:
    """GeoNames has some "uk" names in Latin script (Il'tsi) and none for some towns: those
    get a Cyrillic name with Ukrainian letters from the settlement's other names."""
    if "uk" in own and not CYRILLIC.search(own["uk"]):
        del own["uk"]
    if "uk" not in own:
        name = next(
            (
                n
                for n in alternates
                if UKRAINIAN_LETTERS.search(n) and not RUSSIAN_LETTERS.search(n)
            ),
            None,
        )
        if name:
            own["uk"] = name


def settlements(path: Path, member: str, skip_countries: set[str]) -> Iterator[list[str]]:
    for row in rows(path, member):
        if row[6] == "P" and row[7] not in SKIP_CODES and row[8] not in skip_countries:
            yield row


def main() -> None:
    import json

    with SessionLocal() as session:
        source = upsert_source(session, SOURCE_NAME, SOURCE_URL, SOURCE_LICENSE)
        connection = session.connection().connection.driver_connection
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TEMP TABLE settlement_load (
                    id integer PRIMARY KEY, name text, names jsonb, keys text, country text,
                    population integer, lat double precision, lon double precision
                ) ON COMMIT DROP
            """)
            files = [(download(c), f"{c}.txt", c) for c in FULL_COUNTRIES]
            files.append((download(WORLD_FILE), f"{WORLD_FILE}.txt", None))
            seen: set[int] = set()
            for path, member, country in files:
                batch = [
                    row
                    for row in settlements(path, member, set() if country else set(COUNTRIES))
                    if int(row[0]) not in seen
                ]
                ids = {int(row[0]) for row in batch}
                seen |= ids
                names = local_names(country, ids) if country else {}
                with cursor.copy(
                    "COPY settlement_load (id, name, names, keys, country, population, lat, lon)"
                    " FROM STDIN"
                ) as copy:
                    for row in batch:
                        geoname_id = int(row[0])
                        own = names.get(geoname_id, {})
                        fix_ukrainian(own, row[3].split(","))
                        keys = " | ".join(
                            dict.fromkeys([row[1], row[2], *own.values(), *row[3].split(",")])
                        )
                        copy.write_row(
                            (
                                geoname_id,
                                row[1],
                                json.dumps(own, ensure_ascii=False),
                                keys,
                                row[8],
                                int(row[14] or 0),
                                float(row[4]),
                                float(row[5]),
                            )
                        )
                print(f"{country or WORLD_FILE}: {len(batch)} settlements")
        session.execute(LOAD, {"source_id": source.id})
        print("assigning regions ...")
        for statement in ASSIGN_REGIONS:
            session.execute(statement)
        unplaced = session.scalar(text("SELECT count(*) FROM settlement WHERE region_id IS NULL"))
        total = session.scalar(text("SELECT count(*) FROM settlement"))
        session.commit()
        print(f"{total} settlements, {unplaced} outside our regions")


if __name__ == "__main__":
    main()
