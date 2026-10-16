"""Import first-level regions (oblasts, voivodeships...) from Natural Earth into `region` (adm1).

Regions are attached to their country by the ISO 3166-2 code prefix, so Crimea (UA-43) and
Sevastopol (UA-40), which Natural Earth lists under Russia de facto, belong to Ukraine here,
matching the country layer (Ukraine point of view).

Where Natural Earth's units are small (French departments, Italian and Spanish provinces, UK
council areas, Belgian provinces), they are merged into the regions listed in
data/regions.json (Brittany, Sicily, Catalonia, Wales ...), the level regional languages and
dialects are tied to.

Run from backend/ after the countries importer:  uv run python -m app.importers.natural_earth_admin1
"""

import json
from collections import defaultdict
from pathlib import Path

import httpx2
import shapefile
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.importers.common import RAW_DIR, upsert_source
from app.models import Region

DATASET = "ne_10m_admin_1_states_provinces"
BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/10m_cultural"
SOURCE_NAME = "Natural Earth 1:10m Admin 1 States, Provinces"
SOURCE_URL = "https://www.naturalearthdata.com/"
SOURCE_LICENSE = "Public domain"

# ISO 3166-2 country prefix -> our country region code. Ukraine and the neighbours where
# Ukrainian dialects are spoken (Lemko and Nadsian in Poland and Slovakia, Hutsul and
# Bukovynian in Romania); Western European countries with regional languages and dialects.
COUNTRIES = {
    "UA": "UKR",
    "PL": "POL",
    "SK": "SVK",
    "RO": "ROU",
    "DE": "DEU",
    "AT": "AUT",
    "CH": "CHE",
    "NL": "NLD",
    "BE": "BEL",
    "FR": "FRA",
    "IT": "ITA",
    "ES": "ESP",
    "GB": "GBR",
    # The United States: regional English (soda / pop / coke)
    "US": "USA",
    # Canada: Quebec French (char, fin de semaine)
    "CA": "CAN",
}
# Countries whose units are merged into the regions of data/regions.json
MERGED = {"BE", "FR", "IT", "ES", "GB"}
MERGED_REGIONS_FILE = Path(__file__).parent / "data" / "regions.json"
# Units far from the country's mainland (Caribbean Netherlands)
OVERSEAS = {"NL-SX", "NL-BQ1", "NL-BQ2", "NL-BQ3"}

# Natural Earth names that are wrong or ambiguous
NAME_FIXES = {
    "UA-32": ("Kyiv Oblast", "Київська область"),
    "UA-30": ("Kyiv", "Київ"),
}

UPSERT_REGION = text("""
    INSERT INTO region (name_en, name_uk, level, code, parent_id, geom, label_point, label_rank)
    VALUES (:name_en, :name_uk, 'adm1', :code, :parent_id,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(
                ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)), 3)),
            ST_SetSRID(ST_MakePoint(:label_x, :label_y), 4326), :label_rank)
    ON CONFLICT (level, code) DO UPDATE
    SET name_en = EXCLUDED.name_en, name_uk = EXCLUDED.name_uk, parent_id = EXCLUDED.parent_id,
        geom = EXCLUDED.geom, label_point = EXCLUDED.label_point,
        label_rank = EXCLUDED.label_rank
""")


UPSERT_MERGED_REGION = text("""
    WITH merged AS (
        SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Union(
                   ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(unit), 4326)))), 3)) AS geom
        FROM unnest(CAST(:geojsons AS text[])) AS unit
    )
    INSERT INTO region (name_en, name_uk, level, code, parent_id, geom, label_point, label_rank)
    SELECT :name_en, :name_uk, 'adm1', :code, :parent_id, geom, ST_PointOnSurface(geom),
           :label_rank
    FROM merged
    ON CONFLICT (level, code) DO UPDATE
    SET name_en = EXCLUDED.name_en, name_uk = EXCLUDED.name_uk, parent_id = EXCLUDED.parent_id,
        geom = EXCLUDED.geom, label_point = EXCLUDED.label_point,
        label_rank = EXCLUDED.label_rank
""")


def merged_regions() -> dict[str, dict]:
    regions = json.loads(MERGED_REGIONS_FILE.read_text(encoding="utf-8"))
    regions.pop("_comment", None)
    return regions


def download(target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("shp", "shx", "dbf", "prj"):
        path = target_dir / f"{DATASET}.{ext}"
        if path.exists():
            continue
        print(f"Downloading {path.name} ...")
        response = httpx2.get(f"{BASE_URL}/{DATASET}.{ext}", follow_redirects=True, timeout=300)
        response.raise_for_status()
        path.write_bytes(response.content)
    return target_dir / DATASET


def english_name(name: str) -> str:
    # Natural Earth uses transliterations like "Ivano-Frankivs'k"; drop the apostrophes.
    return name.replace("'", "")


def main() -> None:
    reader = shapefile.Reader(str(download(RAW_DIR / "natural_earth")), encoding="utf-8")

    with SessionLocal() as session:
        upsert_source(session, SOURCE_NAME, SOURCE_URL, SOURCE_LICENSE)
        parents = {
            code: session.scalar(
                select(Region.id).where(Region.level == "country", Region.code == code)
            )
            for code in COUNTRIES.values()
        }
        missing = [code for code, region_id in parents.items() if region_id is None]
        if missing:
            raise SystemExit(f"Import countries first, missing: {missing}")

        merged = merged_regions()
        units: dict[str, list[str]] = defaultdict(list)  # merged region code -> unit shapes
        ranks: dict[str, int] = {}
        count = 0
        for shape_record in reader.iterShapeRecords():
            attrs = shape_record.record.as_dict()
            code = attrs["iso_3166_2"] or ""
            prefix = code.split("-")[0]
            country = COUNTRIES.get(prefix)
            if country is None:
                continue
            if code in OVERSEAS:
                continue
            if prefix in MERGED:
                for region_code, region in merged.items():
                    conditions = region["select"]
                    if isinstance(conditions[0], str):
                        conditions = [conditions]  # one [field, value] pair
                    if region_code.startswith(prefix) and all(
                        attrs[field].strip() == value for field, value in conditions
                    ):
                        units[region_code].append(json.dumps(shape_record.shape.__geo_interface__))
                        ranks[region_code] = min(ranks.get(region_code, 99), attrs["labelrank"])
                continue
            name_en, name_uk = NAME_FIXES.get(
                code, (english_name(attrs["name"]), attrs.get("name_uk") or None)
            )
            session.execute(
                UPSERT_REGION,
                {
                    "code": code,
                    "name_en": name_en,
                    "name_uk": name_uk,
                    "parent_id": parents[country],
                    "geojson": json.dumps(shape_record.shape.__geo_interface__),
                    "label_x": attrs["longitude"],
                    "label_y": attrs["latitude"],
                    "label_rank": attrs["labelrank"],
                },
            )
            count += 1
        for region_code, shapes in units.items():
            names = merged[region_code]["names"]
            session.execute(
                UPSERT_MERGED_REGION,
                {
                    "code": region_code,
                    "name_en": names["en"],
                    "name_uk": names["uk"],
                    "parent_id": parents[COUNTRIES[region_code.split("-")[0]]],
                    "geojsons": shapes,
                    "label_rank": ranks[region_code],
                },
            )
            count += 1
        missing_regions = sorted(set(merged) - set(units))
        if missing_regions:
            print(f"  warning: no Natural Earth units for {missing_regions}")
        # Merged regions dropped from data/regions.json (England, now split into its regions)
        stale = (
            session.execute(
                text("""
                DELETE FROM region WHERE level = 'adm1' AND split_part(code, '-', 1) = ANY(:merged)
                  AND NOT (code = ANY(:codes)) RETURNING code
            """),
                {"merged": sorted(MERGED), "codes": sorted(units)},
            )
            .scalars()
            .all()
        )
        if stale:
            print(f"  removed regions no longer in data/regions.json: {stale}")
        session.commit()

    print(f"Imported {count} first-level regions.")


if __name__ == "__main__":
    main()
