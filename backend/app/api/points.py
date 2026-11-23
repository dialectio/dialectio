"""Points on the map: where members say a word is said, shown before any editor checks it.

A point is a word at a settlement, merged with the same word's marks up to `NEAR_KM` around it.
A member who names only an oblast or a country marks its seat (capital), labelled with the
region's name.
Its weight is what makes it visible from further out:

- each member who says "they say it here" counts their vote weight in the word's variety
  (member 0.5, speaker 1, trusted 2, expert 3);
- "yes" votes cast on the point's card (or on another point of the word within `NEAR_KM`) add
  their weight, "no" votes take it away; votes cast elsewhere (the word list) count for the
  word's points in the voter's region (oblast, or country); votes of the point's own members
  count once (as marks).

Weight > 0 shows the point at village zoom, >= `DISTRICT_WEIGHT` from district zoom,
>= `OBLAST_WEIGHT` from oblast zoom, approved words too. "No" votes that bring it to 0 or below
grey it out at village zoom (people there can still say "yes"); below `HIDE_WEIGHT` it hides.
When a member's submission gathers `PROMOTE_WEIGHT` in all, it becomes a public draft of its
variety ("≈" in the word list), as if an editor had let it through (`promote`).
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException, status
from geoalchemy2 import functions as geo
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.gold import voter_hash
from app.api.lexicon import SessionDep
from app.api.trust import member_weight
from app.api.votes import comment_counts, tallies
from app.api.word_actions import log_change, others_of, snapshot
from app.models import (
    APPROVED,
    ON_MAP_STATUSES,
    PENDING,
    PUBLIC_STATUSES,
    SUBMITTED,
    Concept,
    Form,
    FormPlace,
    Region,
    Settlement,
    User,
    Variety,
    Vote,
)

router = APIRouter(prefix="/api", tags=["points"])

NEAR_KM = 10
DISTRICT_WEIGHT = 1.0
OBLAST_WEIGHT = 3.0
PROMOTE_WEIGHT = 8.0
HIDE_WEIGHT = -1.5  # "no" votes hide a point only below this; above it, it shows greyed out
# Point levels: 0 = village zoom, 1 = district zoom, 2 = oblast zoom (the map picks the zooms)
VILLAGE, DISTRICT, OBLAST = 0, 1, 2
COMMUNITY = "community"  # the change log's actor for promotions


@dataclass
class Mark:
    user_id: int | None
    settlement_id: int
    name: str
    names: dict[str, str]
    lng: float
    lat: float
    region_code: str


@dataclass
class Point:
    center: Mark
    users: set[int] = field(default_factory=set)
    regions: set[str] = field(default_factory=set)
    weight: float = 0.0
    # Some "no" votes count against it
    disputed: bool = False


def km(a: Mark, b: Mark) -> float:
    """Great-circle distance."""
    return km_between((a.lng, a.lat), (b.lng, b.lat))


def marks_of(session: Session, form_ids: list[int]) -> dict[int, list[Mark]]:
    """{form id: its members' marks at settlements}."""
    if not form_ids:
        return {}
    rows = session.execute(
        select(
            FormPlace.form_id,
            FormPlace.user_id,
            Settlement.id,
            Settlement.name,
            Settlement.names,
            geo.ST_X(Settlement.geom),
            geo.ST_Y(Settlement.geom),
            Region.code,
        )
        .join(Settlement, Settlement.id == FormPlace.settlement_id)
        .join(Region, Region.id == FormPlace.region_id)
        .where(FormPlace.form_id.in_(form_ids))
    )
    found: dict[int, list[Mark]] = defaultdict(list)
    for form_id, user_id, sid, name, names, lng, lat, region in rows:
        found[form_id].append(Mark(user_id, sid, name, names or {}, lng, lat, region))
    region_only = session.execute(
        select(FormPlace.form_id, FormPlace.user_id, FormPlace.region_id).where(
            FormPlace.form_id.in_(form_ids), FormPlace.settlement_id.is_(None)
        )
    ).all()
    centers = region_centers(session, {region_id for _, _, region_id in region_only})
    for form_id, user_id, region_id in region_only:
        if (center := centers.get(region_id)) is not None:
            found[form_id].append(Mark(user_id, *center))
    return found


# The settlement standing for a region: its seat (GeoNames PPLC for a country; PPLA, or the
# seat of government PPLG, for an oblast), the biggest when the simplified borders take in a
# neighbour's; an oblast around its seat (Kyiv oblast) takes the seat in its hole; else (no
# seat: Crimea, England's regions, settlements imported without feature codes) the region's
# biggest settlement.
REGION_CENTERS = text("""
    SELECT r.id, s.id, r.name_en, r.name_uk, r.names, ST_X(s.geom), ST_Y(s.geom), r.code
    FROM region r
    CROSS JOIN LATERAL (
        SELECT id, geom FROM (
            (SELECT 1 AS choice, c.id, c.geom FROM settlement c
             WHERE r.level = 'country' AND c.feature = 'PPLC'
               AND (c.region_id = r.id OR ST_Intersects(r.geom, c.geom))
             ORDER BY c.population DESC LIMIT 1)
            UNION ALL
            (SELECT 2, c.id, c.geom FROM settlement c
             WHERE r.level <> 'country' AND c.feature IN ('PPLA', 'PPLC', 'PPLG')
               AND c.region_id = r.id
             ORDER BY c.population DESC LIMIT 1)
            UNION ALL
            (SELECT 3, c.id, c.geom FROM settlement c, ST_Dump(r.geom) part
             WHERE r.level <> 'country' AND c.feature IN ('PPLA', 'PPLC', 'PPLG')
               AND ST_Intersects(ST_MakePolygon(ST_ExteriorRing(part.geom)), c.geom)
             ORDER BY c.population DESC LIMIT 1)
            UNION ALL
            (SELECT 4, c.id, c.geom FROM settlement c WHERE c.region_id = r.id
             ORDER BY c.population DESC LIMIT 1)
        ) candidates
        ORDER BY choice LIMIT 1
    ) s
    WHERE r.id = ANY(:ids)
""")


def region_centers(
    session: Session, region_ids: set[int]
) -> dict[int, tuple[int, str, dict[str, str], float, float, str]]:
    """{region id: (settlement id, name, names, lng, lat, region code)} of the regions' seats,
    named after the region."""
    if not region_ids:
        return {}
    centers = {}
    for rid, sid, name_en, name_uk, names, lng, lat, code in session.execute(
        REGION_CENTERS, {"ids": list(region_ids)}
    ):
        own = {**(names or {}), "en": name_en}
        if name_uk:
            own["uk"] = name_uk
        centers[rid] = (sid, name_en, own, lng, lat, code)
    return centers


@dataclass
class CastVote:
    voter: str
    region: str | None
    # +weight for "yes", -weight for "no"
    weight: float
    # (lng, lat) of the map point it was cast on, if any
    place: tuple[float, float] | None


class Weights:
    """Members' weights per variety, and vote weights per form (cached)."""

    def __init__(self, session: Session, form_ids: list[int]) -> None:
        self.session = session
        self.members: dict[tuple[int, str], float] = {}
        self.votes: dict[int, list[CastVote]] = defaultdict(list)
        if form_ids:
            for form_id, voter, region, value, weight, lng, lat in session.execute(
                select(
                    Vote.form_id,
                    Vote.voter,
                    Vote.region_code,
                    Vote.value,
                    Vote.weight,
                    geo.ST_X(Settlement.geom),
                    geo.ST_Y(Settlement.geom),
                )
                .outerjoin(Settlement, Settlement.id == Vote.settlement_id)
                .where(Vote.form_id.in_(form_ids))
            ):
                self.votes[form_id].append(
                    CastVote(
                        voter,
                        region,
                        weight if value > 0 else -weight,
                        (lng, lat) if lng is not None else None,
                    )
                )

    def member(self, user_id: int, variety: str) -> float:
        key = (user_id, variety)
        if key not in self.members:
            user = self.session.get(User, user_id)
            self.members[key] = member_weight(self.session, user, variety) if user else 0.0
        return self.members[key]

    def counted(self, form_id: int, users: set[int]) -> list[CastVote]:
        """The form's votes, leaving out those of members who already count as marks."""
        own = {voter_hash(f"user:{user_id}") for user_id in users}
        return [v for v in self.votes[form_id] if v.voter not in own]

    def votes_on(self, form_id: int, point: "Point") -> list[CastVote]:
        """The votes a point counts: those cast on a map point within NEAR_KM of it, and those
        cast elsewhere (the word list) by voters living in its region."""
        return [
            v
            for v in self.counted(form_id, point.users)
            if (
                km_between(v.place, (point.center.lng, point.center.lat)) <= NEAR_KM
                if v.place
                else v.region in point.regions
            )
        ]


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lng, lat)."""
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlat, dlng = lat2 - lat1, math.radians(b[0] - a[0])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def points_of(marks: list[Mark], form_id: int, variety: str, weights: Weights) -> list[Point]:
    """The form's marks merged into points: the busiest settlements first, each nearby mark
    joins the first point within NEAR_KM."""
    by_settlement: dict[int, list[Mark]] = defaultdict(list)
    for mark in marks:
        by_settlement[mark.settlement_id].append(mark)
    points: list[Point] = []
    for group in sorted(by_settlement.values(), key=lambda g: -len(g)):
        point = next((p for p in points if km(p.center, group[0]) <= NEAR_KM), None)
        if point is None:
            point = Point(center=group[0])
            points.append(point)
        point.users.update(m.user_id for m in group if m.user_id is not None)
        point.regions.add(group[0].region_code)
    for point in points:
        votes = weights.votes_on(form_id, point)
        point.weight = sum(weights.member(u, variety) for u in point.users) + sum(
            v.weight for v in votes
        )
        point.disputed = any(v.weight < 0 for v in votes)
    return points


def level_of(point: Point) -> int | None:
    """The zoom level a point shows from: by its weight only. An editor's approval says the
    word belongs to the variety, not that it is said at this place (violet on the map).
    A point that "no" votes brought to 0 or below stays at village zoom, greyed out, so that
    people there can still say "yes", until it falls to HIDE_WEIGHT."""
    if point.weight >= OBLAST_WEIGHT:
        return OBLAST
    if point.weight >= DISTRICT_WEIGHT:
        return DISTRICT
    if point.weight > 0 or (point.disputed and point.weight > HIDE_WEIGHT):
        return VILLAGE
    return None


@router.get("/concepts/{concept_id}/points")
def concept_points(session: SessionDep, concept_id: int) -> dict[str, Any]:
    """GeoJSON points of the concept's words where members say them."""
    if session.get(Concept, concept_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    forms = {
        form.id: form
        for form in session.scalars(
            select(Form)
            .join(FormPlace, FormPlace.form_id == Form.id)
            .where(Form.concept_id == concept_id, Form.status.in_(ON_MAP_STATUSES))
            .distinct()
        )
    }
    ids = list(forms)
    marks = marks_of(session, ids)
    weights = Weights(session, ids)
    counted = tallies(session, ids)
    discussed = comment_counts(session, ids)
    features = []
    for form_id, form in forms.items():
        variety: Variety = form.variety
        tally = counted.get(form_id)
        for point in points_of(marks.get(form_id, []), form_id, variety.code, weights):
            level = level_of(point)
            if level is None:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [point.center.lng, point.center.lat],
                    },
                    "properties": {
                        "form_id": form_id,
                        "spelling": form.spelling,
                        "variety_code": variety.code,
                        "variety_en": variety.name_en,
                        "variety_uk": variety.name_uk,
                        "variety_names": variety.names,
                        "settlement_id": point.center.settlement_id,
                        "place": point.center.name,
                        "place_names": point.center.names,
                        "people": len(point.users),
                        "weight": round(point.weight, 2),
                        "disputed": point.weight <= 0,
                        "level": level,
                        "unverified": form.status != APPROVED,
                        "votes_yes": tally.yes if tally else 0,
                        "votes_no": tally.no if tally else 0,
                        "community": tally.community if tally else None,
                        "comments": discussed.get(form_id, 0),
                    },
                }
            )
    # Heavier points first: the map draws them on top
    features.sort(key=lambda f: -f["properties"]["weight"])
    return {"type": "FeatureCollection", "features": features}


def total_weight(session: Session, form: Form) -> float:
    """Every member who says where the word is said, and all its votes."""
    users = set(
        session.scalars(
            select(FormPlace.user_id).where(
                FormPlace.form_id == form.id, FormPlace.user_id.is_not(None)
            )
        )
    )
    weights = Weights(session, [form.id])
    variety = form.variety.code
    return sum(weights.member(u, variety) for u in users) + sum(
        v.weight for v in weights.counted(form.id, users)
    )


def promote(session: Session, form: Form) -> bool:
    """A submission with enough weight becomes a public draft of its variety."""
    if form.status != SUBMITTED or total_weight(session, form) < PROMOTE_WEIGHT:
        return False
    before = snapshot(form)
    form.status = PENDING
    # The variety's main word when it has none yet
    form.is_primary = not any(
        o.is_primary and o.status in PUBLIC_STATUSES for o in others_of(session, form)
    )
    log_change(session, form, "community", before, None, actor_name=COMMUNITY)
    return True
