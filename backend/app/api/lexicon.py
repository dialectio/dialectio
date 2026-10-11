from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.api.labels import build_labels
from app.api.schemas import (
    AudioOut,
    ConceptDetail,
    ConceptLink,
    ConceptSummary,
    FeaturedConcept,
    FormOut,
    LanguageForms,
    SearchHit,
)
from app.db.session import get_session
from app.models import PENDING, PUBLIC_STATUSES, Concept, Form, Variety, Vote, community_status

router = APIRouter(prefix="/api", tags=["lexicon"])

# Sources whose words nobody has checked; shown with an "approximate" mark on the site.
MACHINE_SOURCE_NAME = "Dialectio machine drafts (unverified)"
UNVERIFIED_SOURCES = {
    "Wikidata item labels",
    MACHINE_SOURCE_NAME,
    # Croatian/Bosnian guessed from Wiktionary's joint Serbo-Croatian table
    "Wiktionary translations (Serbo-Croatian, unverified)",
}

SessionDep = Annotated[Session, Depends(get_session)]

# Rank: exact match 3, prefix match 2, otherwise trigram similarity (0..1).
# Matches word spellings in any language and concept glosses (en/uk).
SEARCH = text("""
    WITH candidates AS (
        SELECT f.concept_id, f.spelling AS matched, f.variety_id, f.is_primary
        FROM form f
        WHERE f.status IN ('approved', 'pending')
          AND (lower(f.spelling) LIKE :prefix ESCAPE '\\' OR lower(f.spelling) % :q)
        UNION ALL
        SELECT c.id, g.gloss, NULL, true
        FROM concept c, LATERAL (VALUES (c.gloss_en), (c.gloss_uk)) AS g(gloss)
        WHERE g.gloss IS NOT NULL
          AND (lower(g.gloss) LIKE :prefix ESCAPE '\\' OR similarity(lower(g.gloss), :q) > 0.4)
    ), scored AS (
        SELECT *,
               CASE WHEN lower(matched) = :q THEN 3
                    WHEN lower(matched) LIKE :prefix ESCAPE '\\' THEN 2
                    ELSE similarity(lower(matched), :q) END AS score
        FROM candidates
    )
    SELECT DISTINCT ON (concept_id) concept_id, matched, variety_id, score
    FROM scored
    ORDER BY concept_id, score DESC,
             variety_id = (SELECT id FROM variety WHERE iso639_3 = :prefer) DESC NULLS LAST,
             is_primary DESC
""")


SIMILARITY = "0.4"  # minimal trigram similarity of a fuzzy match


def like_prefix(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


@router.get("/search")
def search(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    # ISO 639-3 code of the language to prefer when the same spelling exists in several
    # languages (e.g. "вода" is both Ukrainian and Russian); usually the UI language.
    prefer: Annotated[str, Query(max_length=3)] = "ukr",
) -> list[SearchHit]:
    needle = q.strip().lower()
    if not needle:
        return []
    params = {"q": needle, "prefix": like_prefix(needle), "prefer": prefer}
    # "%" (trigram similarity above this threshold) can use the trigram index on spellings.
    session.execute(
        text("SELECT set_config('pg_trgm.similarity_threshold', :t, true)"), {"t": SIMILARITY}
    )
    rows = session.execute(SEARCH, params).all()
    rows = sorted(rows, key=lambda r: r.score, reverse=True)[:limit]

    concepts = {
        c.id: c
        for c in session.scalars(
            select(Concept).where(Concept.id.in_([r.concept_id for r in rows]))
        )
    }
    varieties = {
        v.id: v
        for v in session.scalars(
            select(Variety).where(Variety.id.in_({r.variety_id for r in rows if r.variety_id}))
        )
    }
    hits = []
    for row in rows:
        variety = varieties.get(row.variety_id)
        hits.append(
            SearchHit(
                concept=ConceptSummary.model_validate(concepts[row.concept_id]),
                matched_spelling=row.matched,
                matched_language_en=variety.name_en if variety else "English",
                matched_language_uk=variety.name_uk if variety else None,
                matched_language_names=variety.names if variety else {},
            )
        )
    return hits


@router.get("/concepts")
def list_concepts(session: SessionDep) -> list[ConceptLink]:
    """All concepts that have a page (used for the sitemap)."""
    concepts = session.scalars(
        select(Concept).where(Concept.slug.is_not(None)).order_by(Concept.slug)
    )
    return [ConceptLink.model_validate(c) for c in concepts]


# Concepts whose dialect words differ the most: the home page's word of the day and examples.
FEATURED = text("""
    SELECT c.id, c.slug, c.gloss_en, c.glosses,
           -- concepts without a Ukrainian label fall back to the main Ukrainian word
           coalesce(c.gloss_uk, (
               SELECT f.spelling FROM form f JOIN variety v ON v.id = f.variety_id
               WHERE f.concept_id = c.id AND v.code = 'ukr' AND f.is_primary
                 AND f.status IN ('approved', 'pending')
               LIMIT 1)) AS gloss_uk,
           array_agg(w.spelling ORDER BY w.varieties DESC, w.spelling) AS examples
    FROM (
        SELECT f.concept_id, lower(f.spelling) AS spelling, count(*) AS varieties
        FROM form f JOIN variety v ON v.id = f.variety_id
        WHERE v.kind = 'dialect' AND f.status IN ('approved', 'pending')
        GROUP BY f.concept_id, lower(f.spelling)
    ) w
    JOIN concept c ON c.id = w.concept_id
    WHERE c.slug IS NOT NULL
    GROUP BY c.id
    HAVING count(*) >= :min_words
    ORDER BY count(*) DESC, c.slug
    LIMIT :limit
""")


@router.get("/concepts/featured")
def featured_concepts(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=50)] = 12
) -> list[FeaturedConcept]:
    """Concepts with the most different dialect words, e.g. potato: бульба, бараболя, крумплі."""
    rows = session.execute(FEATURED, {"min_words": 2, "limit": limit}).mappings()
    return [FeaturedConcept(**row) for row in rows]


@router.get("/concepts/by-slug/{slug}")
def concept_by_slug(session: SessionDep, slug: str) -> ConceptDetail:
    concept = session.scalar(select(Concept).where(Concept.slug == slug))
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return build_detail(session, concept)


@router.get("/concepts/{concept_id}")
def concept_detail(session: SessionDep, concept_id: int) -> ConceptDetail:
    concept = session.get(Concept, concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return build_detail(session, concept)


def build_detail(session: Session, concept: Concept) -> ConceptDetail:
    forms = session.scalars(
        select(Form)
        .where(Form.concept_id == concept.id, Form.status.in_(PUBLIC_STATUSES))
        .options(
            selectinload(Form.audio),
            selectinload(Form.source),
            selectinload(Form.variety).selectinload(Variety.regions),
            selectinload(Form.variety).selectinload(Variety.parent),
        )
        .order_by(Form.variety_id, Form.is_primary.desc(), Form.spelling)
    ).all()

    votes = {
        form_id: (yes, no)
        for form_id, yes, no in session.execute(
            select(
                Vote.form_id,
                func.count().filter(Vote.value > 0),
                func.count().filter(Vote.value < 0),
            )
            .where(Vote.form_id.in_([f.id for f in forms]))
            .group_by(Vote.form_id)
        )
    }

    languages: dict[int, LanguageForms] = {}
    for form in forms:
        variety = form.variety
        entry = languages.get(variety.id)
        if entry is None:
            entry = languages[variety.id] = LanguageForms(
                variety_id=variety.id,
                code=variety.code,
                kind=variety.kind,
                parent_code=variety.parent.code if variety.parent else None,
                iso639_3=variety.iso639_3,
                name_en=variety.name_en,
                name_uk=variety.name_uk,
                names=variety.names,
                region_codes=sorted(r.code for r in variety.regions),
                forms=[],
            )
        source = form.source.name if form.source else None
        yes, no = votes.get(form.id, (0, 0))
        entry.forms.append(
            FormOut(
                id=form.id,
                spelling=form.spelling,
                ipa=form.ipa,
                transliteration=form.transliteration,
                is_primary=form.is_primary,
                external_id=form.external_id,
                source=source,
                unverified=source in UNVERIFIED_SOURCES or form.status == PENDING,
                votes_yes=yes,
                votes_no=no,
                community=community_status(yes, no),
                audio=[AudioOut.model_validate(a) for a in form.audio],
            )
        )

    labels = build_labels(session, concept.id)
    summary = ConceptSummary.model_validate(concept)
    return ConceptDetail(
        **summary.model_dump(),
        languages=sort_languages(list(languages.values())),
        labels=labels,
        related=related_concepts(session, concept),
    )


RELATED_FEATURED = 6
RELATED_POOL = 40
NEIGHBOURS = text("""
    (SELECT slug, gloss_en, gloss_uk, glosses FROM concept
     WHERE slug < :slug ORDER BY slug DESC LIMIT 1)
    UNION ALL
    (SELECT slug, gloss_en, gloss_uk, glosses FROM concept
     WHERE slug > :slug ORDER BY slug LIMIT 1)
""")


def related_concepts(session: Session, concept: Concept) -> list[ConceptLink]:
    """Links from a word page to other word pages.

    Words with dialect variants come first; each page shows a different window of them, so
    links spread over all of them. The alphabetical neighbours chain every page to the next,
    so crawlers can reach all of them.
    """
    if not concept.slug:
        return []
    pool = [
        row
        for row in session.execute(FEATURED, {"min_words": 2, "limit": RELATED_POOL}).mappings()
        if row["id"] != concept.id
    ]
    start = concept.id % len(pool) if pool else 0
    window = (pool[start:] + pool[:start])[:RELATED_FEATURED]
    related = [
        ConceptLink(
            slug=r["slug"], gloss_en=r["gloss_en"], gloss_uk=r["gloss_uk"], glosses=r["glosses"]
        )
        for r in window
    ]
    seen = {link.slug for link in related}
    for row in session.execute(NEIGHBOURS, {"slug": concept.slug}).mappings():
        if row["slug"] not in seen:
            related.append(ConceptLink(**row))
    return related


def sort_languages(languages: list[LanguageForms]) -> list[LanguageForms]:
    """Languages by English name; each language's dialects right after it, by name."""
    roots = {lang.code: lang.code.split("-")[0] for lang in languages}
    names = {lang.code: lang.name_en for lang in languages}

    def key(lang: LanguageForms) -> tuple[str, bool, str]:
        root = roots[lang.code]
        return (names.get(root, lang.name_en), lang.code != root, lang.name_en)

    return sorted(languages, key=key)
