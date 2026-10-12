"""What visitors have done for the dictionary: checked words, words and recordings they added,
where they live (the "Community" page). Only totals and the names contributors chose to
sign their words with are public, nothing about single voters."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.editor import CONTRIBUTOR_SOURCE_NAME
from app.api.lexicon import SessionDep
from app.models.feedback import CONFIRM_MIN, CONFIRM_SHARE

router = APIRouter(prefix="/api", tags=["community"])

# Most active regions and dialects shown, and contributors thanked by name
TOP = 15
CONTRIBUTORS = 100
RECENT_DAYS = 30

TOTALS = text("""
    SELECT
        (SELECT count(*) FROM vote) AS votes,
        (SELECT count(DISTINCT voter) FROM vote) AS voters,
        (SELECT count(*) FROM vote WHERE created_at > now() - make_interval(days => :days))
            AS recent_votes,
        (SELECT count(*) FROM report) AS reports,
        (SELECT count(*) FROM (
            SELECT form_id FROM vote GROUP BY form_id
            HAVING count(*) FILTER (WHERE value > 0) >= :confirm_min
               AND count(*) FILTER (WHERE value > 0) >= :confirm_share * count(*)
        ) confirmed) AS confirmed,
        (SELECT count(*) FROM form f JOIN source s ON s.id = f.source_id
          WHERE s.name = :contributors AND f.status IN ('approved', 'pending')) AS words,
        (SELECT count(*) FROM audio a JOIN source s ON s.id = a.source_id
           JOIN form f ON f.id = a.form_id
          WHERE s.name = :contributors AND NOT a.is_synthetic
            AND f.status IN ('approved', 'pending')) AS recordings
""")

# Votes by the region the voters said they live in
REGIONS = text("""
    SELECT r.code, r.name_en, r.name_uk, r.names, count(*) AS votes
    FROM vote v
    JOIN region r ON r.code = v.region_code
    GROUP BY r.code, r.name_en, r.name_uk, r.names
    ORDER BY votes DESC, r.code
""")

# Votes on the words of each dialect
DIALECTS = text("""
    SELECT va.code, va.name_en, va.name_uk, va.names, count(*) AS votes
    FROM vote v
    JOIN form f ON f.id = v.form_id
    JOIN variety va ON va.id = f.variety_id
    WHERE va.kind = 'dialect'
    GROUP BY va.code, va.name_en, va.name_uk, va.names
    ORDER BY votes DESC, va.code
    LIMIT :top
""")

# Names under public words and recordings, with how much each person added
CONTRIBUTOR_NAMES = text("""
    SELECT name, count(*) FILTER (WHERE kind = 'word') AS words,
           count(*) FILTER (WHERE kind = 'recording') AS recordings
    FROM (
        SELECT trim(f.contributor) AS name, 'word' AS kind
        FROM form f
        WHERE f.contributor IS NOT NULL AND f.status IN ('approved', 'pending')
        UNION ALL
        SELECT trim(a.speaker), 'recording'
        FROM audio a
        JOIN source s ON s.id = a.source_id
        JOIN form f ON f.id = a.form_id
        WHERE s.name = :contributors AND a.speaker IS NOT NULL AND NOT a.is_synthetic
          AND f.status IN ('approved', 'pending')
    ) contributions
    WHERE name <> ''
    GROUP BY name
    ORDER BY count(*) DESC, name
    LIMIT :limit
""")


class Totals(BaseModel):
    votes: int
    voters: int
    recent_votes: int
    reports: int
    confirmed: int
    words: int
    recordings: int


class Activity(BaseModel):
    code: str
    name_en: str
    name_uk: str | None
    names: dict[str, str]
    votes: int


class Contributor(BaseModel):
    name: str
    words: int
    recordings: int


class Community(BaseModel):
    totals: Totals
    recent_days: int
    regions: list[Activity]
    dialects: list[Activity]
    contributors: list[Contributor]


@router.get("/community")
def get_community(session: SessionDep) -> Community:
    totals = session.execute(
        TOTALS,
        {
            "days": RECENT_DAYS,
            "confirm_min": CONFIRM_MIN,
            "confirm_share": CONFIRM_SHARE,
            "contributors": CONTRIBUTOR_SOURCE_NAME,
        },
    ).one()
    return Community(
        totals=Totals.model_validate(totals._asdict()),
        recent_days=RECENT_DAYS,
        # All regions: the map colours each one
        regions=[Activity.model_validate(r._asdict()) for r in session.execute(REGIONS)],
        dialects=[
            Activity.model_validate(r._asdict()) for r in session.execute(DIALECTS, {"top": TOP})
        ],
        contributors=[
            Contributor.model_validate(r._asdict())
            for r in session.execute(
                CONTRIBUTOR_NAMES,
                {"contributors": CONTRIBUTOR_SOURCE_NAME, "limit": CONTRIBUTORS},
            )
        ],
    )
