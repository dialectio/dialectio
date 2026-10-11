"""trigram index for word search

Revision ID: b264de5e0aa8
Revises: 94ef854a72b0
Create Date: 2026-10-11 17:31:24.588762

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b264de5e0aa8"
down_revision: str | Sequence[str] | None = "94ef854a72b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Word search matches spellings by prefix (LIKE) and by trigram similarity (%).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_form_spelling_trgm ON form "
        "USING gin (lower(spelling) gin_trgm_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_form_spelling_trgm")
