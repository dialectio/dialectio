"""Changes to words made by editors and experts, each written to the change log.

Only our own words can be changed (editor words, drafts, members' submissions); words
imported from Wikidata or Wiktionary are fixed at their source. `actor` is the expert who
acts, or None for the editors.
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR, MEDIA_URL_PREFIX
from app.importers.common import upsert_source
from app.models import APPROVED, PENDING, PUBLIC_STATUSES, SUBMITTED, Form, FormChange, User

EDITOR_SOURCE_NAME = "Dialectio editors"
EDITOR_SOURCE_URL = "https://github.com/dialectio/dialectio"
# Own data stays closed until the project decides on an open license.
EDITOR_SOURCE_LICENSE = "All rights reserved (Dialectio)"
# Drafts proposed for review (e.g. generated); they become editor words once approved.
SUGGESTION_SOURCE_NAME = "Dialectio suggestions (draft)"
# Members' submissions (see app.api.contribute)
CONTRIBUTOR_SOURCE_NAME = "Dialectio contributors"
OWN_SOURCES = (EDITOR_SOURCE_NAME, SUGGESTION_SOURCE_NAME, CONTRIBUTOR_SOURCE_NAME)
EDITORS = "editors"  # the change log's actor for the editors


def snapshot(form: Form) -> dict[str, Any]:
    return {
        "spelling": form.spelling,
        "ipa": form.ipa,
        "status": form.status,
        "primary": form.is_primary,
    }


def log_change(
    session: Session,
    form: Form,
    action: str,
    before: dict[str, Any],
    actor: User | None,
    after: dict[str, Any] | None = None,
) -> None:
    session.add(
        FormChange(
            form_id=form.id,
            concept_id=form.concept_id,
            variety_code=form.variety.code,
            spelling=form.spelling,
            action=action,
            before=before,
            after=snapshot(form) if after is None else after,
            user_id=actor.id if actor else None,
            actor=actor.name if actor else EDITORS,
        )
    )


def own_form(session: Session, form_id: int) -> Form:
    form = session.get(Form, form_id)
    if form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
    if form.source is None or form.source.name not in OWN_SOURCES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only editor words and drafts can be changed"
        )
    return form


def others_of(session: Session, form: Form) -> list[Form]:
    """The concept's other words in the same variety."""
    return list(
        session.scalars(
            select(Form).where(
                Form.concept_id == form.concept_id,
                Form.variety_id == form.variety_id,
                Form.id != form.id,
            )
        )
    )


def log_added(session: Session, form: Form, actor: User | None) -> None:
    session.flush()
    log_change(session, form, "add", {}, actor)


def approve(session: Session, form: Form, actor: User | None) -> None:
    if form.status not in (PENDING, SUBMITTED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts and submissions can be approved")
    before = snapshot(form)
    if form.status == PENDING:
        # A reviewed draft is an editor's word from now on.
        form.source = upsert_source(
            session, EDITOR_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
        )
    # Members' words keep their source (and the member's name) for attribution.
    # An approved word is added as a variant; it only becomes the main word if there is none.
    form.is_primary = not any(
        o.is_primary and o.status in PUBLIC_STATUSES for o in others_of(session, form)
    )
    form.status = APPROVED
    log_change(session, form, "approve", before, actor)


def make_primary(session: Session, form: Form, actor: User | None) -> None:
    """The main word for its concept and variety (the others become variants)."""
    if form.status not in PUBLIC_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Approve the submission first")
    before = snapshot(form)
    for other in others_of(session, form):
        other.is_primary = False
    form.is_primary = True
    log_change(session, form, "primary", before, actor)


def change_spelling(
    session: Session, form: Form, spelling: str | None, ipa: str | None, actor: User | None
) -> None:
    """Fix a word's spelling (typo, capital letter) without losing its recordings."""
    if spelling is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Spelling is empty")
    if any(o.spelling == spelling for o in others_of(session, form)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This word already exists")
    before = snapshot(form)
    if spelling != form.spelling:
        # Synthetic audio says the old spelling; the TTS importer makes a new one later.
        # Real recordings stay: the speaker said the word, only its spelling was wrong.
        for audio in [a for a in form.audio if a.is_synthetic]:
            form.audio.remove(audio)
    form.spelling = spelling
    form.ipa = ipa
    log_change(session, form, "spelling", before, actor)


def delete(session: Session, form: Form, actor: User | None) -> None:
    """Remove a word (a rejected submission or draft, or a wrong editor word)."""
    before = snapshot(form)
    log_change(session, form, "reject" if form.status != APPROVED else "delete", before, actor, {})
    was_primary = form.is_primary
    concept_id, variety_id = form.concept_id, form.variety_id
    # Members' recordings are our own files; imported audio points elsewhere.
    for audio in form.audio:
        if audio.url.startswith(f"{MEDIA_URL_PREFIX}/contrib/"):
            (MEDIA_DIR / audio.url.removeprefix(f"{MEDIA_URL_PREFIX}/")).unlink(missing_ok=True)
    session.delete(form)
    session.flush()
    if was_primary:
        # Promote another word (oldest id) so the concept keeps a primary form in this variety.
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
