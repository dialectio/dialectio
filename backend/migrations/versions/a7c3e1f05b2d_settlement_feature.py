"""settlement feature code (capitals and oblast seats)

Revision ID: a7c3e1f05b2d
Revises: 5d5ef9e6d6cc
Create Date: 2026-11-23 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c3e1f05b2d'
down_revision: str | Sequence[str] | None = '5d5ef9e6d6cc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('settlement', sa.Column('feature', sa.String(length=10), nullable=True))
    # Capitals and seats, where a mark with only an oblast or a country goes on the map
    op.create_index(
        'ix_settlement_seat', 'settlement', ['feature'],
        postgresql_where=sa.text("feature IN ('PPLA', 'PPLC', 'PPLG')"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_settlement_seat', table_name='settlement')
    op.drop_column('settlement', 'feature')
