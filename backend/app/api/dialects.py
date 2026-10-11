"""Dialect pages: the list of dialects and each dialect's territory and words."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.api.lexicon import UNVERIFIED_SOURCES, SessionDep

router = APIRouter(prefix="/api/dialects", tags=["dialects"])


class DialectSummary(BaseModel):
    code: str
    kind: str  # "dialect_group" or "dialect"
    name_en: str
    name_uk: str | None
    parent_code: str | None
    words: int
    region_codes: list[str] = []


class DialectRegion(BaseModel):
    code: str
    name_en: str
    name_uk: str | None
    lon: float
    lat: float


class DialectWord(BaseModel):
    slug: str
    gloss_en: str
    gloss_uk: str | None
    spelling: str
    # The standard Ukrainian word for the same concept, if any
    standard: str | None
    unverified: bool
    has_audio: bool


class DialectDetail(DialectSummary):
    parent_name_en: str | None
    parent_name_uk: str | None
    regions: list[DialectRegion]
    # [west, south, east, north] of the dialect's territory
    bounds: list[float] | None
    words_list: list[DialectWord]


LIST = text("""
    SELECT v.code, v.kind, v.name_en, v.name_uk, p.code AS parent_code,
           (SELECT count(*) FROM form f
            WHERE f.variety_id = v.id AND f.status IN ('approved', 'pending')) AS words,
           coalesce((SELECT array_agg(r.code ORDER BY r.code)
                     FROM variety_region vr JOIN region r ON r.id = vr.region_id
                     WHERE vr.variety_id = v.id), '{}') AS region_codes
    FROM variety v
    LEFT JOIN variety p ON p.id = v.parent_id
    WHERE v.kind IN ('dialect_group', 'dialect')
    ORDER BY v.code
""")

REGIONS = text("""
    SELECT r.code, r.name_en, r.name_uk, ST_X(r.label_point) AS lon, ST_Y(r.label_point) AS lat
    FROM region r JOIN variety_region vr ON vr.region_id = r.id
    WHERE vr.variety_id = :variety_id
    ORDER BY r.code
""")

BOUNDS = text("""
    SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e)
    FROM (SELECT ST_Extent(r.geom) AS e
          FROM region r JOIN variety_region vr ON vr.region_id = r.id
          WHERE vr.variety_id = :variety_id) AS extent
""")

WORDS = text("""
    SELECT c.slug, c.gloss_en, c.gloss_uk, f.spelling,
           (SELECT s.spelling FROM form s JOIN variety u ON u.id = s.variety_id
            WHERE s.concept_id = c.id AND u.code = 'ukr' AND s.is_primary
              AND s.status IN ('approved', 'pending')
            LIMIT 1) AS standard,
           (f.status = 'pending' OR src.name = ANY(:unverified_sources)) AS unverified,
           EXISTS (SELECT 1 FROM audio a WHERE a.form_id = f.id) AS has_audio
    FROM form f
    JOIN concept c ON c.id = f.concept_id
    LEFT JOIN source src ON src.id = f.source_id
    WHERE f.variety_id = :variety_id AND f.status IN ('approved', 'pending')
      AND c.slug IS NOT NULL
    ORDER BY coalesce(c.gloss_uk, c.gloss_en), f.is_primary DESC, f.spelling
""")


@router.get("")
def list_dialects(session: SessionDep) -> list[DialectSummary]:
    return [DialectSummary(**row) for row in session.execute(LIST).mappings()]


@router.get("/{code}")
def dialect_detail(session: SessionDep, code: str) -> DialectDetail:
    row = (
        session.execute(
            text("""
            SELECT v.id, v.code, v.kind, v.name_en, v.name_uk, p.code AS parent_code,
                   p.name_en AS parent_name_en, p.name_uk AS parent_name_uk
            FROM variety v LEFT JOIN variety p ON p.id = v.parent_id
            WHERE v.code = :code AND v.kind = 'dialect'
        """),
            {"code": code},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Dialect not found")

    params = {"variety_id": row["id"]}
    regions = [DialectRegion(**r) for r in session.execute(REGIONS, params).mappings()]
    bounds = session.execute(BOUNDS, params).first()
    words = [
        DialectWord(**w)
        for w in session.execute(
            WORDS, {**params, "unverified_sources": list(UNVERIFIED_SOURCES)}
        ).mappings()
    ]
    return DialectDetail(
        **{k: v for k, v in row.items() if k != "id"},
        words=len(words),
        region_codes=[r.code for r in regions],
        regions=regions,
        bounds=list(bounds) if bounds and bounds[0] is not None else None,
        words_list=words,
    )
