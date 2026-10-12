# ruff: noqa: E501  (generated SQL)
"""accent and script insensitive search

Revision ID: da27400e93ee
Revises: 5a3d48caec19
Create Date: 2026-10-12 20:50:47.404331

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'da27400e93ee'
down_revision: str | Sequence[str] | None = '5a3d48caec19'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# search_key(): the spelling without accents and in Latin script, so that "Worterbuch" finds
# "Wörterbuch" and "kartoplia" finds "картопля" (Ukrainian national romanization, 2010).
SEARCH_KEY = """
CREATE OR REPLACE FUNCTION search_key(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$
    SELECT replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(translate(public.unaccent('public.unaccent', lower(t)), 'абвгґдезиіклмнопрстуфыэ', 'abvhgdezyiklmnoprstufye'), 'ж', 'zh'), 'х', 'kh'), 'ц', 'ts'), 'ч', 'ch'), 'ш', 'sh'), 'щ', 'shch'), 'є', 'ie'), 'ї', 'i'), 'й', 'i'), 'ю', 'iu'), 'я', 'ia'), 'ь', ''), 'ъ', ''), 'ё', 'e'), '’', ''), '''', ''), 'ʼ', '')
$$
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(SEARCH_KEY)
    op.execute("DROP INDEX IF EXISTS ix_form_spelling_trgm")
    op.execute(
        "CREATE INDEX ix_form_search_key_trgm ON form USING gin (search_key(spelling) gin_trgm_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_form_search_key_trgm")
    op.execute(
        "CREATE INDEX ix_form_spelling_trgm ON form USING gin (lower(spelling) gin_trgm_ops)"
    )
    op.execute("DROP FUNCTION IF EXISTS search_key(text)")
