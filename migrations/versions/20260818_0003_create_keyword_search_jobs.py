"""Create persistent keyword search jobs.

Revision ID: 20260818_0003
Revises: 20260818_0002
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0003"
down_revision: str | Sequence[str] | None = "20260818_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "keyword_search_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("query", sa.String(200), nullable=False),
        sa.Column("locale", sa.String(20), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("matches_per_video", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("requested_count > 0"),
        sa.CheckConstraint("matches_per_video > 0"),
        sa.CheckConstraint("status IN ('processing','completed','failed')"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_keyword_search_jobs_status", "keyword_search_jobs", ["status"])
    op.create_table(
        "keyword_search_job_videos",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("keyword_matches", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position >= 0"),
        sa.CheckConstraint("status IN ('loading','matched','no_match','failed')"),
        sa.ForeignKeyConstraint(["job_id"], ["keyword_search_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["youtube_videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "position"),
        sa.UniqueConstraint("job_id", "video_id"),
    )
    op.create_index(
        "ix_keyword_search_job_videos_job_id",
        "keyword_search_job_videos",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_keyword_search_job_videos_job_id", table_name="keyword_search_job_videos")
    op.drop_table("keyword_search_job_videos")
    op.drop_index("ix_keyword_search_jobs_status", table_name="keyword_search_jobs")
    op.drop_table("keyword_search_jobs")
