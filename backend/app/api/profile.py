"""A member's profile: their languages and dialects, the words they added, their votes;
changing the name shown under their words; what deleting the account removes."""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text

from app.api.accounts import SessionDep, require_member, sign_contributions
from app.api.expert import Role, roles_of
from app.api.gold import voter_hash
from app.api.speaker import root
from app.api.trust import LanguageTrust, language_trust
from app.models import Form, Vote

router = APIRouter(prefix="/api/profile", tags=["accounts"])

MAX_CONTRIBUTIONS = 50

VARIETIES = text("""
    SELECT mv.variety_code AS code, v.kind, v.name_en, v.name_uk, v.names,
           mv.tested_at IS NOT NULL AS tested
    FROM member_variety mv JOIN variety v ON v.code = mv.variety_code
    WHERE mv.user_id = :user_id
    -- languages, then dialects (each with its tested ones first)
    ORDER BY v.kind = 'dialect', mv.tested_at IS NULL, v.name_en
""")

CONTRIBUTIONS = text("""
    SELECT f.spelling, f.status, c.slug, c.gloss_en, c.gloss_uk, c.glosses,
           v.code AS variety_code, v.name_en AS variety_name_en,
           v.name_uk AS variety_name_uk, v.names AS variety_names,
           EXISTS (SELECT 1 FROM audio a WHERE a.form_id = f.id) AS recorded
    FROM form f
    JOIN concept c ON c.id = f.concept_id
    JOIN variety v ON v.id = f.variety_id
    WHERE f.contributor_id = :user_id
    ORDER BY f.id DESC
    LIMIT :limit
""")


class MemberVarietyOut(BaseModel):
    code: str
    kind: str
    name_en: str
    name_uk: str | None
    names: dict[str, str] = {}
    tested: bool


class Contribution(BaseModel):
    spelling: str
    status: str  # submitted (waiting for an editor), approved, pending
    slug: str | None
    gloss_en: str
    gloss_uk: str | None
    glosses: dict[str, str] = {}
    variety_code: str
    variety_name_en: str
    variety_name_uk: str | None
    variety_names: dict[str, str] = {}
    recorded: bool


class Profile(BaseModel):
    varieties: list[MemberVarietyOut]
    contributions: list[Contribution]
    contribution_count: int
    votes: int
    # Per language the member speaks: how far they are from "trusted"
    trust: list[LanguageTrust]
    roles: list[Role]  # expert applications and expertise


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


@router.get("")
def get_profile(request: Request, session: SessionDep) -> Profile:
    user = require_member(request, session)
    params = {"user_id": user.id, "limit": MAX_CONTRIBUTIONS}
    varieties = [MemberVarietyOut(**r) for r in session.execute(VARIETIES, params).mappings()]
    languages = dict.fromkeys(root(v.code) for v in varieties if v.tested)
    return Profile(
        varieties=varieties,
        contributions=[
            Contribution(**r) for r in session.execute(CONTRIBUTIONS, params).mappings()
        ],
        contribution_count=session.scalar(
            select(func.count()).where(Form.contributor_id == user.id)
        )
        or 0,
        votes=session.scalar(
            select(func.count()).where(Vote.voter == voter_hash(f"user:{user.id}"))
        )
        or 0,
        trust=[language_trust(session, user.id, language) for language in languages],
        roles=roles_of(session, user.id),
    )


@router.put("/name", status_code=status.HTTP_204_NO_CONTENT)
def rename(data: NameIn, request: Request, session: SessionDep) -> None:
    """The name shown under the member's words and recordings, old ones included."""
    user = require_member(request, session)
    if not data.name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_name")
    user.name = data.name
    sign_contributions(session, user.id, data.name)
    session.commit()
