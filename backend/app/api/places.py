"""Settlements for "where do they say it?": search by name and the nearest one to a point.

"My location" is sent in the request body (not the URL, so it stays out of access logs),
matched to the nearest settlement and not stored.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session

router = APIRouter(prefix="/api/settlements", tags=["settlements"])

SessionDep = Annotated[Session, Depends(get_session)]

LIMIT = 10
# "My location" further than this from any settlement we know finds nothing (degrees, ~30 km)
NEAREST_MAX_DEGREES = 0.3


class SettlementOption(BaseModel):
    id: int
    name: str
    names: dict[str, str]
    # The oblast (or the country, where we have no oblasts) it lies in
    region_code: str
    region_en: str
    region_uk: str | None
    region_names: dict[str, str]
    # Its country, when region_code is an oblast
    country_code: str | None
    country_en: str | None
    country_uk: str | None
    country_names: dict[str, str] | None


COLUMNS = """
    s.id, s.name, s.names,
    r.code AS region_code, r.name_en AS region_en, r.name_uk AS region_uk,
    r.names AS region_names,
    c.code AS country_code, c.name_en AS country_en, c.name_uk AS country_uk,
    c.names AS country_names
    FROM settlement s
    JOIN region r ON r.id = s.region_id
    LEFT JOIN region c ON c.id = r.parent_id
"""

# Any of its names contains the query; a name that is the query, then one that starts with
# it, then the bigger settlement
SEARCH = text(f"""
    SELECT {COLUMNS}
    WHERE search_key(s.keys) LIKE '%' || search_key(:q) || '%'
    ORDER BY ('| ' || search_key(s.keys) || ' |') LIKE '%| ' || search_key(:q) || ' |%' DESC,
             ('| ' || search_key(s.keys)) LIKE '%| ' || search_key(:q) || '%' DESC,
             s.population DESC, s.id
    LIMIT :limit
""")

# The index orders by degrees (a degree of longitude is shorter than one of latitude): of the
# nearest few that way, the nearest in metres
NEAREST = text(f"""
    SELECT {COLUMNS}
    WHERE s.id IN (
        SELECT id FROM settlement
        WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :max_degrees)
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        LIMIT 20)
    ORDER BY ST_Distance(s.geom::geography, ST_MakePoint(:lon, :lat)::geography)
    LIMIT 1
""")


@router.get("")
def search_settlements(
    session: SessionDep, q: Annotated[str, Query(min_length=2, max_length=100)]
) -> list[SettlementOption]:
    query = q.strip()
    if len(query) < 2:
        return []
    rows = session.execute(SEARCH, {"q": query, "limit": LIMIT}).mappings()
    return [SettlementOption(**row) for row in rows]


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


@router.post("/nearest")
def nearest_settlement(session: SessionDep, point: Point) -> SettlementOption:
    row = (
        session.execute(
            NEAREST, {"lat": point.lat, "lon": point.lon, "max_degrees": NEAREST_MAX_DEGREES}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No settlement nearby")
    return SettlementOption(**row)
