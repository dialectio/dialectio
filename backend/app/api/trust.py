"""How much a member's vote counts on a word, and how far they are from the next level.

member 0.5 → speaker of the word's language or dialect (test) 1 → trusted 2: a speaker with
at least TRUSTED_VOTES votes in the language whose last control answers there are at least
TRUSTED_ACCURACY right (TRUSTED_WINDOW answers, at least TRUSTED_MIN_ANSWERS of them); it is
lost again when the accuracy drops → expert of the variety or its language 3 (an editor
approved them). The quiz still comes first: a member who failed it counts nothing.
"""

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.gold import voter_hash
from app.api.speaker import is_speaker, root
from app.models import (
    EXPERT,
    EXPERT_WEIGHT,
    MEMBER_WEIGHT,
    SPEAKER_WEIGHT,
    TRUSTED_WEIGHT,
    ExpertRole,
    Form,
    GoldAnswer,
    User,
    Variety,
    Vote,
)

TRUSTED_VOTES = 50
TRUSTED_WINDOW = 40
TRUSTED_MIN_ANSWERS = 10
TRUSTED_ACCURACY = 0.85


class LanguageTrust(BaseModel):
    language: str
    speaker: bool
    votes: int
    answers: int  # control answers counted (the last TRUSTED_WINDOW at most)
    accuracy: float | None
    trusted: bool


def expert_scope(session: Session, user_id: int) -> list[str]:
    """The varieties a member is an expert of (a language covers its dialects)."""
    return list(
        session.scalars(
            select(ExpertRole.variety_code).where(
                ExpertRole.user_id == user_id, ExpertRole.status == EXPERT
            )
        )
    )


def covers(scope: list[str], variety: str) -> bool:
    return variety in scope or root(variety) in scope


def language_trust(session: Session, user_id: int, language: str) -> LanguageTrust:
    voter = voter_hash(f"user:{user_id}")
    votes = session.scalar(
        select(func.count())
        .select_from(Vote)
        .join(Form, Form.id == Vote.form_id)
        .join(Variety, Variety.id == Form.variety_id)
        .where(Vote.voter == voter, func.split_part(Variety.code, "-", 1) == language)
    )
    last = list(
        session.scalars(
            select(GoldAnswer.correct)
            .where(GoldAnswer.voter == voter, GoldAnswer.language == language)
            .order_by(GoldAnswer.created_at.desc())
            .limit(TRUSTED_WINDOW)
        )
    )
    accuracy = sum(last) / len(last) if last else None
    speaker = is_speaker(session, user_id, language)
    trusted = (
        speaker
        and votes >= TRUSTED_VOTES
        and len(last) >= TRUSTED_MIN_ANSWERS
        and accuracy is not None
        and accuracy >= TRUSTED_ACCURACY
    )
    return LanguageTrust(
        language=language,
        speaker=speaker,
        votes=votes,
        answers=len(last),
        accuracy=accuracy,
        trusted=trusted,
    )


def member_weight(session: Session, user: User, variety: str) -> float:
    """The weight of a member's vote on a word of `variety` (the quiz passed)."""
    if covers(expert_scope(session, user.id), variety):
        return EXPERT_WEIGHT
    if not is_speaker(session, user.id, variety):
        return MEMBER_WEIGHT
    if language_trust(session, user.id, root(variety)).trusted:
        return TRUSTED_WEIGHT
    return SPEAKER_WEIGHT
