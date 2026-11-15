"""Points on the map: where members say a word is said, shown before any editor checks it.

A point is a word at a settlement, merged with the same word's marks up to `NEAR_KM` around it.
Its weight is what makes it visible from further out:

- each member who says "they say it here" counts their vote weight in the word's variety
  (member 0.5, speaker 1, trusted 2, expert 3);
- "yes" votes from visitors who live in the point's region (oblast, or country) add their
  weight, their "no" votes take it away; votes of the point's own members count once (as marks).

Weight > 0 shows the point at village zoom, >= `DISTRICT_WEIGHT` from district zoom,
>= `OBLAST_WEIGHT` (or an approved word) from oblast zoom; weight <= 0 hides it.
When a member's submission gathers `PROMOTE_WEIGHT` in all, it becomes a public draft of its
variety ("≈" in the word list), as if an editor had let it through (`promote`).
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException, status
from geoalchemy2 import functions as geo
from sqlalchemy import select
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


def km(a: Mark, b: Mark) -> float:
    """Great-circle distance."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat, dlng = lat2 - lat1, math.radians(b.lng - a.lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


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
    return found


class Weights:
    """Members' weights per variety, and vote weights per form and region (cached)."""

    def __init__(self, session: Session, form_ids: list[int]) -> None:
        self.session = session
        self.members: dict[tuple[int, str], float] = {}
        # {form id: [(voter hash, region code, signed weight)]}
        self.votes: dict[int, list[tuple[str, str | None, float]]] = defaultdict(list)
        if form_ids:
            for form_id, voter, region, value, weight in session.execute(
                select(Vote.form_id, Vote.voter, Vote.region_code, Vote.value, Vote.weight).where(
                    Vote.form_id.in_(form_ids)
                )
            ):
                self.votes[form_id].append((voter, region, weight if value > 0 else -weight))

    def member(self, user_id: int, variety: str) -> float:
        key = (user_id, variety)
        if key not in self.members:
            user = self.session.get(User, user_id)
            self.members[key] = member_weight(self.session, user, variety) if user else 0.0
        return self.members[key]

    def votes_from(self, form_id: int, regions: set[str] | None, users: set[int]) -> float:
        """Net vote weight on the form (from these regions only, unless None), leaving out
        the votes of members who already count as marks."""
        own = {voter_hash(f"user:{user_id}") for user_id in users}
        return sum(
            weight
            for voter, region, weight in self.votes[form_id]
            if voter not in own and (regions is None or region in regions)
        )


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
        point.weight = sum(weights.member(u, variety) for u in point.users) + weights.votes_from(
            form_id, point.regions, point.users
        )
    return points


def level_of(form: Form, weight: float) -> int | None:
    if form.status == APPROVED or weight >= OBLAST_WEIGHT:
        return OBLAST
    if weight >= DISTRICT_WEIGHT:
        return DISTRICT
    if weight > 0:
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
            level = level_of(form, point.weight)
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
                        "place": point.center.name,
                        "place_names": point.center.names,
                        "people": len(point.users),
                        "weight": round(point.weight, 2),
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
    return sum(weights.member(u, variety) for u in users) + weights.votes_from(
        form.id, None, users
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
