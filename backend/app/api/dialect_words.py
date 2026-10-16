"""Dialect word pages (/slovo/<word>): what a dialect word means and where it is used.

A dialect word gets a page when it differs from the standard Ukrainian word for the same
concept (Hutsul "ватра" = "вогонь"); spellings are matched case-insensitively. A word can
mean different things in different dialects (Hutsul "губа" = mushroom), so a page lists
every meaning.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.api.dialects import DialectRegion
from app.api.lexicon import UNVERIFIED_SOURCES, SessionDep
from app.api.schemas import AudioOut
from app.models import community_status

router = APIRouter(prefix="/api/dialect-words", tags=["dialect words"])


class DialectRef(BaseModel):
    code: str
    name_en: str
    name_uk: str | None
    names: dict[str, str] = {}


class DialectUse(DialectRef):
    """The word in one dialect: the form visitors vote on."""

    form_id: int
    unverified: bool
    votes_yes: int = 0
    votes_no: int = 0
    community: str | None = None


class OtherWord(BaseModel):
    word: str  # lower case, the key of its own page
    spelling: str  # as written ("Schrippe")
    dialects: list[DialectRef]


class Meaning(BaseModel):
    slug: str
    gloss_en: str
    gloss_uk: str | None
    glosses: dict[str, str] = {}
    standard: str | None  # the standard word of the dialect's language
    dialects: list[DialectUse]
    unverified: bool
    audio: list[AudioOut]
    # Other dialect words for the same concept (each has its own page)
    others: list[OtherWord]


class DialectWordDetail(BaseModel):
    word: str
    meanings: list[Meaning]
    regions: list[DialectRegion]
    bounds: list[float] | None


# Dialect forms that differ from their language's standard word for the concept.
DIALECT_FORMS = """
    SELECT f.id, lower(f.spelling) AS word, f.spelling, f.concept_id, f.status,
           v.id AS variety_id, v.code, v.name_en, v.name_uk, v.names, src.name AS source,
           (SELECT s.spelling FROM form s JOIN variety u ON u.id = s.variety_id
            WHERE s.concept_id = f.concept_id AND u.code = split_part(v.code, '-', 1)
              AND s.is_primary AND s.status IN ('approved', 'pending')
            LIMIT 1) AS standard
    FROM form f
    JOIN variety v ON v.id = f.variety_id AND v.kind = 'dialect'
    LEFT JOIN source src ON src.id = f.source_id
    WHERE f.status IN ('approved', 'pending')
"""

LIST = text(f"""
    SELECT DISTINCT d.word FROM ({DIALECT_FORMS}) d
    JOIN concept c ON c.id = d.concept_id AND c.slug IS NOT NULL
    WHERE d.standard IS NULL OR lower(d.standard) <> d.word
    ORDER BY d.word
""")

FORMS_OF_WORD = text(f"""
    SELECT d.*, c.slug, c.gloss_en, c.gloss_uk, c.glosses FROM ({DIALECT_FORMS}) d
    JOIN concept c ON c.id = d.concept_id AND c.slug IS NOT NULL
    WHERE d.word = :word AND (d.standard IS NULL OR lower(d.standard) <> d.word)
    ORDER BY c.slug, d.code
""")

OTHER_WORDS = text(f"""
    SELECT d.word, d.spelling, d.code, d.name_en, d.name_uk, d.names FROM ({DIALECT_FORMS}) d
    WHERE d.concept_id = :concept_id AND d.word <> :word
      AND (d.standard IS NULL OR lower(d.standard) <> d.word)
    ORDER BY d.word, d.code
""")

# The same synthetic recording is shared by every dialect that spells the word alike.
AUDIO = text("""
    SELECT url, license, speaker, is_synthetic FROM (
        SELECT DISTINCT ON (a.url) a.url, a.license, a.speaker, a.is_synthetic, a.id
        FROM audio a WHERE a.form_id = ANY(:form_ids)
        ORDER BY a.url, a.id
    ) unique_audio
    ORDER BY is_synthetic, id
""")

VOTES = text("""
    SELECT form_id, count(*) FILTER (WHERE value > 0), count(*) FILTER (WHERE value < 0)
    FROM vote WHERE form_id = ANY(:form_ids)
    GROUP BY form_id
""")

REGIONS = text("""
    SELECT DISTINCT r.code, r.name_en, r.name_uk, r.names,
           ST_X(r.label_point) AS lon, ST_Y(r.label_point) AS lat
    FROM region r JOIN variety_region vr ON vr.region_id = r.id
    WHERE vr.variety_id = ANY(:variety_ids)
    ORDER BY r.code
""")

BOUNDS = text("""
    SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e)
    FROM (SELECT ST_Extent(r.geom) AS e
          FROM region r JOIN variety_region vr ON vr.region_id = r.id
          WHERE vr.variety_id = ANY(:variety_ids)) AS extent
""")


@router.get("")
def list_dialect_words(session: SessionDep) -> list[str]:
    """Every dialect word that has a page (for the sitemap)."""
    return list(session.scalars(LIST))


@router.get("/{word}")
def dialect_word(session: SessionDep, word: str) -> DialectWordDetail:
    word = word.strip().lower()
    rows = list(session.execute(FORMS_OF_WORD, {"word": word}).mappings())
    if not rows:
        raise HTTPException(status_code=404, detail="Dialect word not found")

    votes = {
        form_id: (yes, no)
        for form_id, yes, no in session.execute(VOTES, {"form_ids": [r["id"] for r in rows]})
    }
    by_concept: dict[int, list] = {}
    for row in rows:
        by_concept.setdefault(row["concept_id"], []).append(row)

    meanings = []
    for concept_id, forms in by_concept.items():
        first = forms[0]
        others: dict[str, list[DialectRef]] = {}
        spellings: dict[str, str] = {}
        # Other names in the same language's dialects only (pochoclo: palomitas, not pop-corn)
        languages = {f["code"].split("-")[0] for f in forms}
        for other in session.execute(
            OTHER_WORDS, {"concept_id": concept_id, "word": word}
        ).mappings():
            if other["code"].split("-")[0] not in languages:
                continue
            spellings.setdefault(other["word"], other["spelling"])
            others.setdefault(other["word"], []).append(
                DialectRef(
                    code=other["code"],
                    name_en=other["name_en"],
                    name_uk=other["name_uk"],
                    names=other["names"],
                )
            )
        meanings.append(
            Meaning(
                slug=first["slug"],
                gloss_en=first["gloss_en"],
                gloss_uk=first["gloss_uk"],
                glosses=first["glosses"],
                standard=first["standard"],
                dialects=[
                    DialectUse(
                        code=f["code"],
                        name_en=f["name_en"],
                        name_uk=f["name_uk"],
                        names=f["names"],
                        form_id=f["id"],
                        unverified=f["status"] == "pending" or f["source"] in UNVERIFIED_SOURCES,
                        votes_yes=votes.get(f["id"], (0, 0))[0],
                        votes_no=votes.get(f["id"], (0, 0))[1],
                        community=community_status(*votes.get(f["id"], (0, 0))),
                    )
                    for f in forms
                ],
                unverified=all(
                    f["status"] == "pending" or f["source"] in UNVERIFIED_SOURCES for f in forms
                ),
                audio=[
                    AudioOut(**a)
                    for a in session.execute(
                        AUDIO, {"form_ids": [f["id"] for f in forms]}
                    ).mappings()
                ],
                others=[
                    OtherWord(word=w, spelling=spellings[w], dialects=d) for w, d in others.items()
                ],
            )
        )

    variety_ids = list({row["variety_id"] for row in rows})
    bounds = session.execute(BOUNDS, {"variety_ids": variety_ids}).first()
    return DialectWordDetail(
        # Keep the spelling's own capitalisation when all forms agree (names, etc.)
        word=rows[0]["spelling"] if len({r["spelling"] for r in rows}) == 1 else word,
        meanings=meanings,
        regions=[
            DialectRegion(**r)
            for r in session.execute(REGIONS, {"variety_ids": variety_ids}).mappings()
        ],
        bounds=list(bounds) if bounds and bounds[0] is not None else None,
    )
