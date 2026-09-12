"""Add default subtitle languages system configuration.

Revision ID: 20260818_0004
Revises: 20260818_0003
Create Date: 2026-08-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260818_0004"
down_revision: str | Sequence[str] | None = "20260818_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO system_config (key, value) "
        "VALUES ('DEFAULT_SUBTITLE_LANGUAGES', '[\"zh-TW\"]'::json) "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM system_config WHERE key = 'DEFAULT_SUBTITLE_LANGUAGES'"
    )
