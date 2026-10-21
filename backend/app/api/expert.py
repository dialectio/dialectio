"""Experts: speakers an editor approved for a language or dialect review its words.

A tested speaker applies for a variety with a few words about themselves; an editor decides
(app/api/editor.py). An expert sees the variety's submitted words, drafts and mistake reports,
approves or rejects them, fixes spellings of our own words and makes a word the main one.
Approved words can only be deleted by the editors. Everything goes to the change log.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.api import word_actions
from app.api.accounts import SessionDep, require_member
from app.api.editor import EditorForm, SpellingChange, require_editor, to_editor_form
from app.api.speaker import is_speaker
from app.api.trust import covers, expert_scope
from app.api.votes import Tally, tallies
from app.models import (
    APPLIED,
    DECLINED,
    EXPERT,
    PENDING,
    PUBLIC_STATUSES,
    SUBMITTED,
    ExpertRole,
    Form,
    FormChange,
    MemberVariety,
    Report,
    User,
    Variety,
)

router = APIRouter(prefix="/api/expert", tags=["expert"])
# The editors' side: applications, decisions, the whole change log
editor_router = APIRouter(
    prefix="/api/editor", tags=["editor"], dependencies=[Depends(require_editor)]
)

QUEUE_LIMIT = 100
CHANGES_LIMIT = 100


class Role(BaseModel):
    variety_code: str
    variety_name_en: str
    variety_name_uk: str | None
    variety_names: dict[str, str] = {}
    status: str  # applied, expert, declined
    note: str


class ApplicationIn(BaseModel):
    variety: str = Field(max_length=40)
    note: str = Field(min_length=10, max_length=1000)


class ReportOut(BaseModel):
    id: int
    message: str
    created_at: str


class QueueItem(BaseModel):
    form: EditorForm
    concept_slug: str | None
    concept_gloss_en: str
    concept_gloss_uk: str | None
    concept_glosses: dict[str, str] = {}
    variety_code: str
    variety_name_en: str
    variety_name_uk: str | None
    variety_names: dict[str, str] = {}
    yes: float
    no: float
    community: str | None
    reports: list[ReportOut]


class ChangeOut(BaseModel):
    form_id: int | None
    variety_code: str
    spelling: str
    action: str
    before: dict
    after: dict
    actor: str
    created_at: str


def roles_of(session: Session, user_id: int) -> list[Role]:
    rows = session.execute(
        select(ExpertRole, Variety)
        .join(Variety, Variety.code == ExpertRole.variety_code)
        .where(ExpertRole.user_id == user_id)
        .order_by(ExpertRole.created_at)
    )
    return [
        Role(
            variety_code=role.variety_code,
            variety_name_en=variety.name_en,
            variety_name_uk=variety.name_uk,
            variety_names=variety.names,
            status=role.status,
            note=role.note,
        )
        for role, variety in rows
    ]


def require_scope(session: Session, user: User, variety: str) -> None:
    if not covers(expert_scope(session, user.id), variety):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_your_variety")


def expert_form(session: Session, user: User, form_id: int) -> Form:
    form = word_actions.own_form(session, form_id)
    require_scope(session, user, form.variety.code)
    return form


def scope_filter(variety: str):
    """Words of the variety; for a language, its dialects too."""
    return or_(Variety.code == variety, Variety.code.like(f"{variety}-%"))


@router.get("/roles")
def my_roles(request: Request, session: SessionDep) -> list[Role]:
    return roles_of(session, require_member(request, session).id)


@router.post("/applications", status_code=status.HTTP_204_NO_CONTENT)
def apply(data: ApplicationIn, request: Request, session: SessionDep) -> None:
    """Ask to be an expert of a variety; open to speakers who passed its language's test."""
    user = require_member(request, session)
    variety = session.scalar(select(Variety).where(Variety.code == data.variety))
    if variety is None or variety.kind == "dialect_group":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_variety")
    if not is_speaker(session, user.id, data.variety):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "speakers_only")
    statement = insert(ExpertRole).values(
        user_id=user.id, variety_code=data.variety, note=data.note.strip(), status=APPLIED
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["user_id", "variety_code"],
            set_={"note": statement.excluded.note, "status": APPLIED, "decided_at": None},
            # An expert stays one; a declined member may apply again
            where=ExpertRole.status != EXPERT,
        )
    )
    # The variety goes to the languages and dialects they speak (profile)
    session.execute(
        insert(MemberVariety)
        .values(user_id=user.id, variety_code=data.variety)
        .on_conflict_do_nothing()
    )
    session.commit()


@router.get("/queue")
def queue(
    request: Request,
    session: SessionDep,
    variety: Annotated[str, Query(max_length=40)],
) -> list[QueueItem]:
    """Submitted words first, then words with open mistake reports, then drafts."""
    user = require_member(request, session)
    require_scope(session, user, variety)
    open_reports: dict[int, list[Report]] = {}
    for report in session.scalars(
        select(Report)
        .join(Form, Form.id == Report.form_id)
        .join(Variety, Variety.id == Form.variety_id)
        .where(~Report.resolved, scope_filter(variety))
        .order_by(Report.created_at)
    ):
        open_reports.setdefault(report.form_id, []).append(report)
    forms = session.scalars(
        select(Form)
        .join(Variety, Variety.id == Form.variety_id)
        .where(
            scope_filter(variety),
            or_(
                Form.status.in_((SUBMITTED, PENDING)),
                Form.id.in_(list(open_reports)) & Form.status.in_(PUBLIC_STATUSES),
            ),
        )
        .options(
            selectinload(Form.concept),
            selectinload(Form.variety),
            selectinload(Form.source),
            selectinload(Form.audio),
        )
    ).all()
    weights = tallies(session, [f.id for f in forms])
    forms.sort(
        key=lambda f: (
            f.status != SUBMITTED,
            f.id not in open_reports,
            -(weights.get(f.id, Tally()).yes_weight + weights.get(f.id, Tally()).no_weight),
            f.id,
        )
    )
    items = []
    for form in forms[:QUEUE_LIMIT]:
        tally = weights.get(form.id, Tally())
        items.append(
            QueueItem(
                form=to_editor_form(form),
                concept_slug=form.concept.slug,
                concept_gloss_en=form.concept.gloss_en,
                concept_gloss_uk=form.concept.gloss_uk,
                concept_glosses=form.concept.glosses,
                variety_code=form.variety.code,
                variety_name_en=form.variety.name_en,
                variety_name_uk=form.variety.name_uk,
                variety_names=form.variety.names,
                yes=tally.yes_weight,
                no=tally.no_weight,
                community=tally.community,
                reports=[
                    ReportOut(id=r.id, message=r.message, created_at=r.created_at.isoformat())
                    for r in open_reports.get(form.id, [])
                ],
            )
        )
    return items


@router.post("/forms/{form_id}/approve")
def approve(form_id: int, request: Request, session: SessionDep) -> EditorForm:
    user = require_member(request, session)
    form = expert_form(session, user, form_id)
    word_actions.approve(session, form, user)
    session.commit()
    return to_editor_form(form)


@router.post("/forms/{form_id}/primary")
def make_primary(form_id: int, request: Request, session: SessionDep) -> EditorForm:
    user = require_member(request, session)
    form = expert_form(session, user, form_id)
    word_actions.make_primary(session, form, user)
    session.commit()
    return to_editor_form(form)


@router.post("/forms/{form_id}/spelling")
def change_spelling(
    form_id: int, change: SpellingChange, request: Request, session: SessionDep
) -> EditorForm:
    user = require_member(request, session)
    form = expert_form(session, user, form_id)
    word_actions.change_spelling(session, form, change.spelling, change.ipa, user)
    session.commit()
    return to_editor_form(form)


@router.post("/forms/{form_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject(form_id: int, request: Request, session: SessionDep) -> None:
    """Remove a submitted word or a draft (approved words are the editors' to delete)."""
    user = require_member(request, session)
    form = expert_form(session, user, form_id)
    if form.status not in (SUBMITTED, PENDING):
        raise HTTPException(status.HTTP_409_CONFLICT, "editors_only")
    word_actions.delete(session, form, user)
    session.commit()


@router.post("/reports/{report_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
def resolve_report(report_id: int, request: Request, session: SessionDep) -> None:
    user = require_member(request, session)
    report = session.get(Report, report_id)
    form = session.get(Form, report.form_id) if report else None
    if report is None or form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_report")
    require_scope(session, user, form.variety.code)
    report.resolved = True
    session.commit()


def changes(session: Session, variety: str | None, limit: int = CHANGES_LIMIT) -> list[ChangeOut]:
    query = select(FormChange).order_by(FormChange.created_at.desc(), FormChange.id.desc())
    if variety:
        query = query.where(
            or_(FormChange.variety_code == variety, FormChange.variety_code.like(f"{variety}-%"))
        )
    return [
        ChangeOut(
            form_id=c.form_id,
            variety_code=c.variety_code,
            spelling=c.spelling,
            action=c.action,
            before=c.before,
            after=c.after,
            actor=c.actor,
            created_at=c.created_at.isoformat(),
        )
        for c in session.scalars(query.limit(limit))
    ]


@router.get("/changes")
def variety_changes(
    request: Request, session: SessionDep, variety: Annotated[str, Query(max_length=40)]
) -> list[ChangeOut]:
    user = require_member(request, session)
    require_scope(session, user, variety)
    return changes(session, variety)


class Application(BaseModel):
    user_id: int
    name: str
    email: str
    variety_code: str
    variety_name_en: str
    variety_name_uk: str | None
    status: str
    note: str
    created_at: str


class Decision(BaseModel):
    user_id: int
    variety: str = Field(max_length=40)
    status: str = Field(pattern=f"^({EXPERT}|{DECLINED})$")  # declined also takes it back


@editor_router.get("/experts")
def list_experts(session: SessionDep) -> list[Application]:
    """Applications waiting for a decision first, then experts, then declined ones."""
    rows = session.execute(
        select(ExpertRole, User, Variety)
        .join(User, User.id == ExpertRole.user_id)
        .join(Variety, Variety.code == ExpertRole.variety_code)
        .order_by(
            (ExpertRole.status == APPLIED).desc(),
            (ExpertRole.status == EXPERT).desc(),
            ExpertRole.created_at,
        )
    )
    return [
        Application(
            user_id=user.id,
            name=user.name,
            email=user.email,
            variety_code=role.variety_code,
            variety_name_en=variety.name_en,
            variety_name_uk=variety.name_uk,
            status=role.status,
            note=role.note,
            created_at=role.created_at.isoformat(),
        )
        for role, user, variety in rows
    ]


@editor_router.post("/experts/decision", status_code=status.HTTP_204_NO_CONTENT)
def decide(data: Decision, session: SessionDep) -> None:
    role = session.get(ExpertRole, (data.user_id, data.variety))
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_application")
    role.status = data.status
    role.decided_at = datetime.now(UTC)
    session.commit()


@editor_router.get("/changes")
def all_changes(
    session: SessionDep, variety: Annotated[str | None, Query(max_length=40)] = None
) -> list[ChangeOut]:
    """The change log: what editors and experts did to words, newest first."""
    return changes(session, variety, limit=300)
