"""Vote totals of words: how many "yes" / "no" votes (shown) and their weight (decides the
"confirmed by speakers" mark)."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Vote, community_status


@dataclass(frozen=True)
class Tally:
    yes: int = 0
    no: int = 0
    yes_weight: float = 0.0
    no_weight: float = 0.0

    @property
    def community(self) -> str | None:
        return community_status(self.yes_weight, self.no_weight)


def tallies(session: Session, form_ids: list[int]) -> dict[int, Tally]:
    """{form id: its vote tally} for the forms that have votes."""
    if not form_ids:
        return {}
    rows = session.execute(
        select(
            Vote.form_id,
            func.count().filter(Vote.value > 0),
            func.count().filter(Vote.value < 0),
            func.coalesce(func.sum(Vote.weight).filter(Vote.value > 0), 0.0),
            func.coalesce(func.sum(Vote.weight).filter(Vote.value < 0), 0.0),
        )
        .where(Vote.form_id.in_(form_ids))
        .group_by(Vote.form_id)
    )
    return {
        form_id: Tally(yes, no, float(yes_weight), float(no_weight))
        for form_id, yes, no, yes_weight, no_weight in rows
    }
