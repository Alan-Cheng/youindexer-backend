"""Create system_config table.

Revision ID: 20260818_0002
Revises: 20260817_0001
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0002"
down_revision: str | Sequence[str] | None = "20260817_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(255), nullable=False, comment="設定項目名稱"),
        sa.Column(
            "value", sa.JSON(), nullable=False, comment="設定值（JSON 格式）"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="資料建立時間",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="資料更新時間",
        ),
        sa.PrimaryKeyConstraint("key"),
        comment="系統可動態調整的設定參數",
    )
    op.execute(
        "INSERT INTO system_config (key, value) "
        "VALUES ('DEFAULT_YOUTUBE_VIDEO_RESULT_LIMIT', '3'::json)"
    )


def downgrade() -> None:
    op.drop_table("system_config")
