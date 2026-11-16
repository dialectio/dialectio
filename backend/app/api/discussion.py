"""Discussions of a word (a form: the word in one language or dialect).

The discussion opens with the word's card (meaning, source, where people say it, votes), built
from the data, so it stays current. Then members' comments, in any language. Comments show at
once; see app/models/discussion.py for reports and hiding. Editors moderate with the editor
token (`/api/editor/comments`); experts of the word's variety and members with the editor role
hide and restore comments from the discussion itself.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.accounts import current_user, require_member
from app.api.editor import require_editor
from app.api.feedback import check_limit, public_form, voter_hash
from app.api.lexicon import UNVERIFIED_SOURCES
from app.api.trust import covers, expert_scope
from app.api.votes import Tally, tallies
from app.db.session import get_session
from app.models import (
    APPROVED,
    EDITOR,
    HIDDEN,
    HIDE_AFTER,
    MAX_COMMENT,
    ON_MAP_STATUSES,
    VISIBLE,
    Comment,
    CommentReport,
    Form,
    FormPlace,
    Region,
    User,
)
from app.turnstile import require_human

router = APIRouter(prefix="/api", tags=["discussion"])
editor_router = APIRouter(
    prefix="/api/editor", tags=["editor"], dependencies=[Depends(require_editor)]
)

SessionDep = Annotated[Session, Depends(get_session)]

COMMENT_LIMIT = (30, 3600)  # comments per IP per hour
REPORT_LIMIT = (20, 3600)
QUOTE = 160  # characters of the answered comment shown as a quote
EDITOR_LIMIT = 200

EXPERT_BADGE = "expert"
EDITOR_BADGE = "editor"


def can_moderate(session: Session, user: User | None, form: Form) -> bool:
    if user is None:
        return False
    return user.role == EDITOR or covers(expert_scope(session, user.id), form.variety.code)


class Place(BaseModel):
    """Where members say the word: a settlement (names by language) or only a region."""

    names: dict[str, str]  # the settlement's names; empty for a region only
    name: str | None  # the settlement's own name
    region_en: str
    region_uk: str | None
    region_names: dict[str, str]
    count: int  # members who said it is said here


class Card(BaseModel):
    form_id: int
    spelling: str
    ipa: str | None
    variety_code: str
    variety_en: str
    variety_uk: str | None
    variety_names: dict[str, str]
    concept_slug: str | None
    gloss_en: str
    gloss_uk: str | None
    glosses: dict[str, str]
    description_en: str | None
    description_uk: str | None
    descriptions: dict[str, str]
    source: str | None
    source_url: str | None
    license: str | None
    contributor: str | None
    unverified: bool
    votes_yes: int
    votes_no: int
    community: str | None
    places: list[Place]


class Quote(BaseModel):
    id: int
    author: str
    text: str


class CommentOut(BaseModel):
    id: int
    author: str
    badge: str | None  # "expert" (of this variety) or "editor"
    body: str
    created_at: datetime
    edited_at: datetime | None
    reply_to: Quote | None
    mine: bool
    # Only for moderators
    hidden: bool = False
    reports: int = 0


class Discussion(BaseModel):
    card: Card
    comments: list[CommentOut]
    can_moderate: bool


def places_of(session: Session, form_id: int) -> list[Place]:
    rows = session.scalars(
        select(FormPlace)
        .where(FormPlace.form_id == form_id)
        .options(selectinload(FormPlace.settlement), selectinload(FormPlace.region))
    ).all()
    found: dict[tuple, Place] = {}
    for row in rows:
        key = (row.settlement_id, row.region_id)
        if key in found:
            found[key].count += 1
            continue
        region: Region = row.region
        found[key] = Place(
            names=row.settlement.names if row.settlement else {},
            name=row.settlement.name if row.settlement else None,
            region_en=region.name_en,
            region_uk=region.name_uk,
            region_names=region.names,
            count=1,
        )
    return sorted(found.values(), key=lambda p: -p.count)


def card_of(session: Session, form: Form) -> Card:
    concept = form.concept
    source = form.source
    tally = tallies(session, [form.id]).get(form.id, Tally())
    return Card(
        form_id=form.id,
        spelling=form.spelling,
        ipa=form.ipa,
        variety_code=form.variety.code,
        variety_en=form.variety.name_en,
        variety_uk=form.variety.name_uk,
        variety_names=form.variety.names,
        concept_slug=concept.slug,
        gloss_en=concept.gloss_en,
        gloss_uk=concept.gloss_uk,
        glosses=concept.glosses,
        description_en=concept.description_en,
        description_uk=concept.description_uk,
        descriptions=concept.descriptions,
        source=source.name if source else None,
        source_url=source.url if source else None,
        license=source.license if source else None,
        contributor=form.contributor,
        unverified=form.status != APPROVED
        or (source is not None and source.name in UNVERIFIED_SOURCES),
        votes_yes=tally.yes,
        votes_no=tally.no,
        community=tally.community,
        places=places_of(session, form.id),
    )


def badges(session: Session, form: Form, user_ids: set[int]) -> dict[int, str]:
    found: dict[int, str] = {}
    for user in session.scalars(select(User).where(User.id.in_(user_ids))):
        if covers(expert_scope(session, user.id), form.variety.code):
            found[user.id] = EXPERT_BADGE
        elif user.role == EDITOR:
            found[user.id] = EDITOR_BADGE
    return found


def comments_of(
    session: Session, form: Form, viewer: User | None, moderator: bool
) -> list[CommentOut]:
    query = select(Comment, User.name).join(User, User.id == Comment.user_id)
    query = query.where(Comment.form_id == form.id).order_by(Comment.created_at, Comment.id)
    if not moderator:
        query = query.where(Comment.status == VISIBLE)
    rows = session.execute(query).all()
    reports = {}
    if moderator and rows:
        reports = dict(
            session.execute(
                select(CommentReport.comment_id, func.count())
                .where(
                    CommentReport.comment_id.in_([c.id for c, _ in rows]),
                    ~CommentReport.resolved,
                )
                .group_by(CommentReport.comment_id)
            )
            .all()
        )
    by_id = {c.id: (c, name) for c, name in rows}
    marks = badges(session, form, {c.user_id for c, _ in rows})
    result = []
    for comment, name in rows:
        quoted = by_id.get(comment.reply_to_id) if comment.reply_to_id else None
        result.append(
            CommentOut(
                id=comment.id,
                author=name,
                badge=marks.get(comment.user_id),
                body=comment.body,
                created_at=comment.created_at,
                edited_at=comment.edited_at,
                reply_to=Quote(id=quoted[0].id, author=quoted[1], text=excerpt(quoted[0].body))
                if quoted
                else None,
                mine=viewer is not None and comment.user_id == viewer.id,
                hidden=comment.status == HIDDEN,
                reports=reports.get(comment.id, 0),
            )
        )
    return result


def excerpt(text: str) -> str:
    return text if len(text) <= QUOTE else text[: QUOTE - 1].rstrip() + "…"


def word_form(session: Session, form_id: int) -> Form:
    public_form(session, form_id)
    return session.scalars(
        select(Form)
        .where(Form.id == form_id)
        .options(selectinload(Form.concept), selectinload(Form.variety), selectinload(Form.source))
    ).one()


def discussion(session: Session, form: Form, viewer: User | None) -> Discussion:
    moderator = can_moderate(session, viewer, form)
    return Discussion(
        card=card_of(session, form),
        comments=comments_of(session, form, viewer, moderator),
        can_moderate=moderator,
    )


@router.get("/forms/{form_id}/discussion")
def get_discussion(form_id: int, request: Request, session: SessionDep) -> Discussion:
    form = word_form(session, form_id)
    return discussion(session, form, current_user(request, session))


def clean(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("empty")
    return value


class CommentIn(BaseModel):
    body: str = Field(max_length=MAX_COMMENT)
    reply_to: int | None = None
    captcha: str = Field(default="", max_length=2048)  # Turnstile token

    @field_validator("body")
    @classmethod
    def not_empty(cls, value: str) -> str:
        return clean(value)


@router.post("/forms/{form_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(form_id: int, data: CommentIn, request: Request, session: SessionDep) -> Discussion:
    user = require_member(request, session)
    check_limit("comment", request, COMMENT_LIMIT)
    form = word_form(session, form_id)
    require_human(request, data.captcha)
    if data.reply_to is not None:
        answered = session.get(Comment, data.reply_to)
        if answered is None or answered.form_id != form.id or answered.status != VISIBLE:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_comment")
    session.add(
        Comment(form_id=form.id, user_id=user.id, reply_to_id=data.reply_to, body=data.body)
    )
    session.commit()
    return discussion(session, form, user)


def own_comment(session: Session, user: User, comment_id: int) -> Comment:
    comment = session.get(Comment, comment_id)
    if comment is None or comment.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_comment")
    return comment


class CommentEdit(BaseModel):
    body: str = Field(max_length=MAX_COMMENT)

    @field_validator("body")
    @classmethod
    def not_empty(cls, value: str) -> str:
        return clean(value)


@router.patch("/comments/{comment_id}")
def edit_comment(
    comment_id: int, data: CommentEdit, request: Request, session: SessionDep
) -> Discussion:
    user = require_member(request, session)
    comment = own_comment(session, user, comment_id)
    if comment.body != data.body:
        comment.body = data.body
        comment.edited_at = datetime.now(UTC)
        session.commit()
    return discussion(session, word_form(session, comment.form_id), user)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, request: Request, session: SessionDep) -> None:
    user = require_member(request, session)
    session.delete(own_comment(session, user, comment_id))
    session.commit()


class ReportIn(BaseModel):
    reason: str = Field(default="", max_length=1000)
    voter: str | None = Field(default=None, min_length=8, max_length=64)  # a guest's browser id


@router.post("/comments/{comment_id}/report", status_code=status.HTTP_204_NO_CONTENT)
def report_comment(comment_id: int, data: ReportIn, request: Request, session: SessionDep) -> None:
    """Report a comment. Reporting twice changes nothing; HIDE_AFTER members hide it."""
    check_limit("comment_report", request, REPORT_LIMIT)
    comment = session.get(Comment, comment_id)
    if comment is None or comment.status != VISIBLE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_comment")
    member = current_user(request, session)
    if member is None and not data.voter:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "voter")
    reporter = voter_hash(f"user:{member.id}" if member else data.voter)
    exists = session.scalar(
        select(CommentReport.id).where(
            CommentReport.comment_id == comment.id, CommentReport.reporter == reporter
        )
    )
    if exists is not None:
        return
    session.add(
        CommentReport(
            comment_id=comment.id,
            reporter=reporter,
            member=member is not None,
            reason=data.reason.strip(),
        )
    )
    session.flush()
    members = session.scalar(
        select(func.count()).where(
            CommentReport.comment_id == comment.id,
            CommentReport.member,
            ~CommentReport.resolved,
        )
    )
    if members >= HIDE_AFTER:
        comment.status = HIDDEN
        comment.hidden_by = "reports"
    session.commit()


def set_visibility(session: Session, comment: Comment, hidden: bool, by: str) -> None:
    comment.status = HIDDEN if hidden else VISIBLE
    comment.hidden_by = by if hidden else None
    # A decision answers the reports so far
    for report in session.scalars(
        select(CommentReport).where(CommentReport.comment_id == comment.id, ~CommentReport.resolved)
    ):
        report.resolved = True


def moderated_comment(session: Session, request: Request, comment_id: int) -> tuple[Comment, User]:
    user = require_member(request, session)
    comment = session.get(Comment, comment_id)
    form = session.get(Form, comment.form_id) if comment else None
    if comment is None or form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_comment")
    if not can_moderate(session, user, form):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_your_variety")
    return comment, user


@router.post("/comments/{comment_id}/hide")
def hide_comment(comment_id: int, request: Request, session: SessionDep) -> Discussion:
    comment, user = moderated_comment(session, request, comment_id)
    set_visibility(session, comment, True, f"expert:{user.id}")
    session.commit()
    return discussion(session, word_form(session, comment.form_id), user)


@router.post("/comments/{comment_id}/restore")
def restore_comment(comment_id: int, request: Request, session: SessionDep) -> Discussion:
    comment, user = moderated_comment(session, request, comment_id)
    set_visibility(session, comment, False, "")
    session.commit()
    return discussion(session, word_form(session, comment.form_id), user)


# Editors (the editor token)


class ReportOut(BaseModel):
    reason: str
    member: bool
    created_at: datetime


class EditorComment(BaseModel):
    id: int
    form_id: int
    spelling: str
    variety_code: str
    concept_slug: str | None
    author: str
    body: str
    created_at: datetime
    hidden: bool
    hidden_by: str | None
    reports: list[ReportOut]


@editor_router.get("/comments")
def editor_comments(session: SessionDep) -> list[EditorComment]:
    """Comments with open reports or hidden, the newest first."""
    open_reports: dict[int, list[CommentReport]] = {}
    for report in session.scalars(
        select(CommentReport).where(~CommentReport.resolved).order_by(CommentReport.created_at)
    ):
        open_reports.setdefault(report.comment_id, []).append(report)
    rows = session.execute(
        select(Comment, User.name, Form)
        .join(User, User.id == Comment.user_id)
        .join(Form, Form.id == Comment.form_id)
        .where((Comment.status == HIDDEN) | Comment.id.in_(open_reports))
        .options(selectinload(Form.variety), selectinload(Form.concept))
        .order_by(Comment.created_at.desc())
        .limit(EDITOR_LIMIT)
    ).all()
    return [
        EditorComment(
            id=comment.id,
            form_id=form.id,
            spelling=form.spelling,
            variety_code=form.variety.code,
            concept_slug=form.concept.slug,
            author=name,
            body=comment.body,
            created_at=comment.created_at,
            hidden=comment.status == HIDDEN,
            hidden_by=comment.hidden_by,
            reports=[
                ReportOut(reason=r.reason, member=r.member, created_at=r.created_at)
                for r in open_reports.get(comment.id, [])
            ],
        )
        for comment, name, form in rows
        if form.status in ON_MAP_STATUSES
    ]


def any_comment(session: Session, comment_id: int) -> Comment:
    comment = session.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_comment")
    return comment


@editor_router.post("/comments/{comment_id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def editor_hide(comment_id: int, session: SessionDep) -> None:
    set_visibility(session, any_comment(session, comment_id), True, "editor")
    session.commit()


@editor_router.post("/comments/{comment_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def editor_restore(comment_id: int, session: SessionDep) -> None:
    set_visibility(session, any_comment(session, comment_id), False, "")
    session.commit()


@editor_router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def editor_delete(comment_id: int, session: SessionDep) -> None:
    session.delete(any_comment(session, comment_id))
    session.commit()
