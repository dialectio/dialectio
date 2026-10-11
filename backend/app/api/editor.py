"""Word editor: lets trusted editors add forms for concepts (e.g. fill gaps in Ukrainian)
and review draft suggestions (status "pending") before they become public.

Protected by a shared token (settings.editor_token, sent as the X-Editor-Token header).
"""

import secrets
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.lexicon import UNVERIFIED_SOURCES
from app.config import MEDIA_DIR, MEDIA_URL_PREFIX, settings
from app.db.session import get_session
from app.importers.common import upsert_source
from app.models import (
    APPROVED,
    DISPUTED,
    PENDING,
    PUBLIC_STATUSES,
    SUBMITTED,
    Concept,
    Form,
    MissingSearch,
    Report,
    Variety,
    Vote,
    community_status,
)

EDITOR_SOURCE_NAME = "Dialectio editors"
EDITOR_SOURCE_URL = "https://github.com/gmisha777/dialectio"
# Own data stays closed until the project decides on an open license.
EDITOR_SOURCE_LICENSE = "All rights reserved (Dialectio)"
# Drafts proposed for review (e.g. generated); they become editor words once approved.
SUGGESTION_SOURCE_NAME = "Dialectio suggestions (draft)"
# Visitor submissions (see app.api.contribute)
CONTRIBUTOR_SOURCE_NAME = "Dialectio contributors"
OWN_SOURCES = (EDITOR_SOURCE_NAME, SUGGESTION_SOURCE_NAME, CONTRIBUTOR_SOURCE_NAME)

# Varieties shown as hints next to each concept in the editor (standard Ukrainian first,
# useful when editing dialects)
HINT_LANGUAGES = ("ukr", "eng", "pol", "deu", "rus")


def require_editor(x_editor_token: Annotated[str | None, Header()] = None) -> None:
    if not settings.editor_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Editing is disabled")
    if not x_editor_token or not secrets.compare_digest(x_editor_token, settings.editor_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid editor token")


router = APIRouter(prefix="/api/editor", tags=["editor"], dependencies=[Depends(require_editor)])

SessionDep = Annotated[Session, Depends(get_session)]


class EditorForm(BaseModel):
    id: int
    spelling: str
    ipa: str | None
    is_primary: bool
    status: str
    source: str | None
    editable: bool
    # Visitor submissions: who sent it, from where, and their recording
    contributor: str | None = None
    place: str | None = None
    audio_urls: list[str] = []


class Submission(BaseModel):
    form: EditorForm
    concept_id: int
    concept_gloss_en: str
    concept_gloss_uk: str | None
    variety_code: str
    variety_name_en: str
    variety_name_uk: str | None


class EditorConcept(BaseModel):
    id: int
    wikidata_id: str | None
    gloss_en: str
    gloss_uk: str | None
    description_en: str | None
    description_uk: str | None
    hints: dict[str, str]
    forms: list[EditorForm]


class EditorVariety(BaseModel):
    code: str
    kind: str
    name_en: str
    name_uk: str | None
    parent_code: str | None


class NewForm(BaseModel):
    concept_id: int
    variety: str = Field(min_length=2, max_length=40)
    spelling: str = Field(min_length=1, max_length=200)
    ipa: str | None = Field(default=None, max_length=200)

    @field_validator("spelling", "ipa")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        value = value.strip() if value else value
        return value or None


class SpellingChange(BaseModel):
    spelling: str = Field(min_length=1, max_length=200)
    ipa: str | None = Field(default=None, max_length=200)

    @field_validator("spelling", "ipa")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        value = value.strip() if value else value
        return value or None


def get_variety(session: Session, code: str) -> Variety:
    variety = session.scalar(select(Variety).where(Variety.code == code))
    if variety is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown variety {code}")
    return variety


def to_editor_form(form: Form) -> EditorForm:
    source = form.source.name if form.source else None
    return EditorForm(
        id=form.id,
        spelling=form.spelling,
        ipa=form.ipa,
        is_primary=form.is_primary,
        status=form.status,
        source=source,
        editable=source in OWN_SOURCES,
        contributor=form.contributor,
        place=form.note if form.status == SUBMITTED else None,
        audio_urls=[a.url for a in form.audio] if form.status == SUBMITTED else [],
    )


def has_approved_primary(session: Session, concept_id: int, variety_id: int) -> bool:
    return (
        session.scalar(
            select(Form.id).where(
                Form.concept_id == concept_id,
                Form.variety_id == variety_id,
                Form.is_primary,
                Form.status == APPROVED,
            )
        )
        is not None
    )


def get_own_form(session: Session, form_id: int) -> Form:
    form = session.get(Form, form_id)
    if form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
    if form.source is None or form.source.name not in OWN_SOURCES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only editor words and drafts can be changed"
        )
    return form


@router.get("/varieties")
def list_varieties(session: SessionDep) -> list[EditorVariety]:
    """Languages and dialects that can be edited (dialect groups only group dialects)."""
    varieties = session.scalars(
        select(Variety)
        .where(Variety.kind != "dialect_group")
        .options(selectinload(Variety.parent))
        .order_by(Variety.code)
    )
    return [
        EditorVariety(
            code=v.code,
            kind=v.kind,
            name_en=v.name_en,
            name_uk=v.name_uk,
            parent_code=v.parent.code if v.parent else None,
        )
        for v in varieties
    ]


@router.get("/concepts")
def list_concepts(
    session: SessionDep, variety: Annotated[str, Query(min_length=2, max_length=40)] = "ukr"
) -> list[EditorConcept]:
    edited = get_variety(session, variety)
    hint_varieties = {
        v.id: v.code
        for v in session.scalars(select(Variety).where(Variety.code.in_(HINT_LANGUAGES)))
    }
    concepts = session.scalars(select(Concept).order_by(Concept.gloss_en)).all()
    # Only the words that are shown: the edited variety's and the hint languages' main words
    # (loading every language's words would mean hundreds of thousands of rows).
    forms_by_concept: dict[int, list[Form]] = defaultdict(list)
    for form in session.scalars(
        select(Form)
        .where(
            (Form.variety_id == edited.id) | (Form.variety_id.in_(hint_varieties) & Form.is_primary)
        )
        .options(selectinload(Form.source), selectinload(Form.audio))
    ):
        forms_by_concept[form.concept_id].append(form)

    result = []
    for concept in concepts:
        concept_forms = forms_by_concept.get(concept.id, [])
        primary = {
            hint_varieties[f.variety_id]: f.spelling
            for f in concept_forms
            if f.is_primary and f.variety_id in hint_varieties
        }
        hints = {lang: primary[lang] for lang in HINT_LANGUAGES if lang in primary}
        forms = sorted(
            (f for f in concept_forms if f.variety_id == edited.id),
            key=lambda f: (f.status != APPROVED, not f.is_primary, f.spelling),
        )
        result.append(
            EditorConcept(
                id=concept.id,
                wikidata_id=concept.wikidata_id,
                gloss_en=concept.gloss_en,
                gloss_uk=concept.gloss_uk,
                description_en=concept.description_en,
                description_uk=concept.description_uk,
                hints=hints,
                forms=[to_editor_form(f) for f in forms],
            )
        )
    return result


@router.post("/forms", status_code=status.HTTP_201_CREATED)
def add_form(session: SessionDep, payload: NewForm) -> EditorForm:
    if session.get(Concept, payload.concept_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    variety = get_variety(session, payload.variety)

    existing = session.scalars(
        select(Form).where(Form.concept_id == payload.concept_id, Form.variety_id == variety.id)
    ).all()
    if any(f.spelling == payload.spelling for f in existing):
        raise HTTPException(status.HTTP_409_CONFLICT, "This word already exists")

    source = upsert_source(session, EDITOR_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE)
    form = Form(
        concept_id=payload.concept_id,
        variety=variety,
        spelling=payload.spelling,
        ipa=payload.ipa,
        # A new word is added next to the existing ones; the main word only changes on
        # request (see set_primary).
        is_primary=not any(f.is_primary and f.status in PUBLIC_STATUSES for f in existing),
        status=APPROVED,
        source=source,
    )
    session.add(form)
    session.commit()
    return to_editor_form(form)


@router.get("/submissions")
def list_submissions(session: SessionDep) -> list[Submission]:
    """Words sent by visitors, waiting for review (oldest first)."""
    forms = session.scalars(
        select(Form)
        .where(Form.status == SUBMITTED)
        .options(
            selectinload(Form.concept),
            selectinload(Form.variety),
            selectinload(Form.source),
            selectinload(Form.audio),
        )
        .order_by(Form.id)
    )
    return [
        Submission(
            form=to_editor_form(f),
            concept_id=f.concept.id,
            concept_gloss_en=f.concept.gloss_en,
            concept_gloss_uk=f.concept.gloss_uk,
            variety_code=f.variety.code,
            variety_name_en=f.variety.name_en,
            variety_name_uk=f.variety.name_uk,
        )
        for f in forms
    ]


@router.post("/forms/{form_id}/approve")
def approve_form(session: SessionDep, form_id: int) -> EditorForm:
    form = get_own_form(session, form_id)
    if form.status not in (PENDING, SUBMITTED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts and submissions can be approved")
    if form.status == PENDING:
        # A reviewed draft is an editor's word from now on.
        form.source = upsert_source(
            session, EDITOR_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
        )
    # Visitor words keep their source (and the visitor's name) for attribution.
    others = session.scalars(
        select(Form).where(
            Form.concept_id == form.concept_id,
            Form.variety_id == form.variety_id,
            Form.id != form.id,
        )
    ).all()
    # An approved word is added as a variant; it only becomes the main word if there is none.
    form.is_primary = not any(o.is_primary and o.status in PUBLIC_STATUSES for o in others)
    form.status = APPROVED
    session.commit()
    return to_editor_form(form)


@router.post("/forms/{form_id}/primary")
def set_primary(session: SessionDep, form_id: int) -> EditorForm:
    """Make this word the main one for its concept and language (others become variants)."""
    form = get_own_form(session, form_id)
    if form.status not in PUBLIC_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Approve the submission first")
    others = session.scalars(
        select(Form).where(
            Form.concept_id == form.concept_id,
            Form.variety_id == form.variety_id,
            Form.id != form.id,
        )
    )
    for other in others:
        other.is_primary = False
    form.is_primary = True
    session.commit()
    return to_editor_form(form)


@router.post("/forms/{form_id}/spelling")
def change_spelling(session: SessionDep, form_id: int, change: SpellingChange) -> EditorForm:
    """Fix a word's spelling (typo, capital letter) without losing its recordings."""
    form = get_own_form(session, form_id)
    if change.spelling is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Spelling is empty")
    duplicate = session.scalar(
        select(Form.id).where(
            Form.concept_id == form.concept_id,
            Form.variety_id == form.variety_id,
            Form.spelling == change.spelling,
            Form.id != form.id,
        )
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This word already exists")
    if change.spelling != form.spelling:
        # Synthetic audio says the old spelling; the TTS importer makes a new one later.
        # Real recordings stay: the speaker said the word, only its spelling was wrong.
        for audio in [a for a in form.audio if a.is_synthetic]:
            form.audio.remove(audio)
    form.spelling = change.spelling
    form.ipa = change.ipa
    session.commit()
    return to_editor_form(form)


@router.delete("/forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_form(session: SessionDep, form_id: int) -> None:
    form = get_own_form(session, form_id)
    was_primary = form.is_primary
    concept_id, variety_id = form.concept_id, form.variety_id
    # Visitors' recordings are our own files; imported audio points elsewhere.
    for audio in form.audio:
        if audio.url.startswith(f"{MEDIA_URL_PREFIX}/contrib/"):
            (MEDIA_DIR / audio.url.removeprefix(f"{MEDIA_URL_PREFIX}/")).unlink(missing_ok=True)
    session.delete(form)
    session.flush()
    if was_primary:
        # Promote another word (oldest id) so the concept keeps a primary form in this language.
        replacement = session.scalars(
            select(Form)
            .where(
                Form.concept_id == concept_id,
                Form.variety_id == variety_id,
                Form.status.in_(PUBLIC_STATUSES),
            )
            .order_by((Form.status == APPROVED).desc(), Form.id)
        ).first()
        if replacement:
            replacement.is_primary = True
    session.commit()


class ReportOut(BaseModel):
    id: int
    message: str
    region_code: str | None
    created_at: str


class FeedbackItem(BaseModel):
    form: EditorForm
    concept_id: int
    concept_slug: str | None
    concept_gloss_en: str
    concept_gloss_uk: str | None
    variety_code: str
    variety_name_en: str
    variety_name_uk: str | None
    yes: int
    no: int
    community: str | None
    # Votes by the voter's region: {"UA-26": [yes, no]}
    regions: dict[str, list[int]]
    reports: list[ReportOut]


FEEDBACK_LIMIT = 200


@router.get("/feedback")
def list_feedback(session: SessionDep) -> list[FeedbackItem]:
    """Words visitors voted on or reported: disputed ones and open reports first."""
    vote_rows = session.execute(
        select(
            Vote.form_id,
            Vote.region_code,
            func.count().filter(Vote.value > 0),
            func.count().filter(Vote.value < 0),
        ).group_by(Vote.form_id, Vote.region_code)
    ).all()
    votes: dict[int, dict[str | None, list[int]]] = {}
    for form_id, region, yes, no in vote_rows:
        votes.setdefault(form_id, {})[region] = [yes, no]
    reports: dict[int, list[Report]] = {}
    for item in session.scalars(select(Report).where(~Report.resolved).order_by(Report.created_at)):
        reports.setdefault(item.form_id, []).append(item)

    form_ids = set(votes) | set(reports)
    forms = session.scalars(
        select(Form)
        .where(Form.id.in_(form_ids), Form.status.in_(PUBLIC_STATUSES))
        .options(
            selectinload(Form.concept),
            selectinload(Form.variety),
            selectinload(Form.source),
            selectinload(Form.audio),
        )
    ).all()

    items = []
    for form in forms:
        by_region = votes.get(form.id, {})
        yes = sum(v[0] for v in by_region.values())
        no = sum(v[1] for v in by_region.values())
        # On verified words votes say where the word is used ("no" = not said here), so
        # they don't make the word disputed.
        unverified = form.status == PENDING or (
            form.source is not None and form.source.name in UNVERIFIED_SOURCES
        )
        items.append(
            FeedbackItem(
                form=to_editor_form(form),
                concept_id=form.concept.id,
                concept_slug=form.concept.slug,
                concept_gloss_en=form.concept.gloss_en,
                concept_gloss_uk=form.concept.gloss_uk,
                variety_code=form.variety.code,
                variety_name_en=form.variety.name_en,
                variety_name_uk=form.variety.name_uk,
                yes=yes,
                no=no,
                community=community_status(yes, no) if unverified else None,
                regions={code: counts for code, counts in by_region.items() if code},
                reports=[
                    ReportOut(
                        id=r.id,
                        message=r.message,
                        region_code=r.region_code,
                        created_at=r.created_at.isoformat(),
                    )
                    for r in reports.get(form.id, [])
                ],
            )
        )
    items.sort(
        key=lambda i: (i.community != DISPUTED, -len(i.reports), -(i.no - i.yes), -(i.yes + i.no))
    )
    return items[:FEEDBACK_LIMIT]


@router.post("/reports/{report_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
def resolve_report(session: SessionDep, report_id: int) -> None:
    item = session.get(Report, report_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    item.resolved = True
    session.commit()


class MissingOut(BaseModel):
    query: str
    count: int
    last_seen: str


@router.get("/missing")
def list_missing(session: SessionDep) -> list[MissingOut]:
    """What visitors searched for and did not find, most wanted first."""
    rows = session.scalars(
        select(MissingSearch)
        .order_by(MissingSearch.count.desc(), MissingSearch.last_seen.desc())
        .limit(FEEDBACK_LIMIT)
    )
    return [
        MissingOut(query=r.query, count=r.count, last_seen=r.last_seen.isoformat()) for r in rows
    ]


@router.delete("/missing/{query}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_missing(session: SessionDep, query: str) -> None:
    """Remove a query from the list (added to the dictionary, or not worth adding)."""
    row = session.get(MissingSearch, query)
    if row is not None:
        session.delete(row)
        session.commit()
