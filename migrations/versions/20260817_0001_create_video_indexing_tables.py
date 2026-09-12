"""Create video discovery and indexing workflow tables.

Revision ID: 20260817_0001
Revises:
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE_COMMENTS = {
    "youtube_videos": "YouTube 影片主檔與搜尋取得的 metadata",
    "search_queries": "YouTube 關鍵字搜尋歷史",
    "search_query_results": "每次搜尋所包含的影片及顯示順位",
    "transcripts": "每支影片各語言字幕的處理狀態與 MinIO 位置",
    "search_index_jobs": "字幕寫入 OpenSearch 的工作狀態",
    "outbox_events": "可靠發布 Celery 任務的 transactional outbox",
}

COLUMN_COMMENTS = {
    "youtube_videos": {
        "id": "影片內部識別碼",
        "youtube_video_id": "YouTube 影片識別碼",
        "canonical_url": "影片標準網址",
        "title": "影片標題",
        "channel_name": "頻道名稱",
        "channel_url": "頻道網址",
        "thumbnail_url": "縮圖網址",
        "duration_text": "搜尋頁顯示的影片長度文字",
        "duration_seconds": "正規化後的影片長度秒數",
        "published_text": "搜尋頁顯示的發布時間文字",
        "published_at": "正規化後的影片發布時間",
        "view_count_text": "搜尋頁顯示的觀看次數文字",
        "view_count": "正規化後的觀看次數",
        "description": "影片描述摘要",
        "first_discovered_at": "首次被搜尋發現時間",
        "last_seen_at": "最近一次出現在搜尋結果的時間",
        "created_at": "資料建立時間",
        "updated_at": "資料更新時間",
    },
    "search_queries": {
        "id": "搜尋紀錄識別碼",
        "query": "使用者搜尋關鍵字",
        "locale": "搜尋使用的語系",
        "requested_limit": "要求的最大結果數",
        "result_count": "實際取得的結果數",
        "searched_at": "執行搜尋時間",
    },
    "search_query_results": {
        "search_query_id": "搜尋紀錄識別碼",
        "video_id": "YouTube 影片內部識別碼",
        "position": "影片在該次搜尋結果的順位",
    },
    "transcripts": {
        "id": "字幕紀錄識別碼",
        "video_id": "YouTube 影片內部識別碼",
        "language": "字幕目標語言",
        "source_language": "字幕原始語言",
        "source": "字幕來源類型",
        "status": "字幕處理狀態",
        "object_name": "MinIO 字幕物件路徑",
        "content_hash": "字幕內容 SHA-256",
        "segment_count": "字幕片段數",
        "attempt_count": "字幕處理嘗試次數",
        "last_error": "最近一次錯誤訊息",
        "fetched_at": "字幕自來源取得時間",
        "stored_at": "字幕寫入 MinIO 時間",
        "created_at": "資料建立時間",
        "updated_at": "資料更新時間",
    },
    "search_index_jobs": {
        "id": "索引工作識別碼",
        "transcript_id": "字幕紀錄識別碼",
        "index_alias": "OpenSearch 索引別名",
        "status": "索引工作狀態",
        "generation_id": "本次索引內容版本識別碼",
        "chunk_count": "已索引片段數",
        "attempt_count": "索引嘗試次數",
        "last_error": "最近一次錯誤訊息",
        "started_at": "最近一次開始索引時間",
        "indexed_at": "索引成功完成時間",
        "created_at": "資料建立時間",
        "updated_at": "資料更新時間",
    },
    "outbox_events": {
        "id": "Outbox 事件識別碼",
        "event_type": "事件類型",
        "aggregate_type": "事件主體類型",
        "aggregate_id": "事件主體識別碼",
        "deduplication_key": "防止重複建立事件的唯一鍵",
        "payload": "事件 JSON 內容",
        "status": "事件發布狀態",
        "attempt_count": "事件發布嘗試次數",
        "available_at": "最早可發布時間",
        "published_at": "成功發布至訊息佇列時間",
        "last_error": "最近一次發布錯誤",
        "created_at": "資料建立時間",
        "updated_at": "資料更新時間",
    },
}


def _add_database_comments() -> None:
    for table_name, comment in TABLE_COMMENTS.items():
        op.execute(f"COMMENT ON TABLE {table_name} IS '{comment}'")
    for table_name, columns in COLUMN_COMMENTS.items():
        for column_name, comment in columns.items():
            op.execute(f"COMMENT ON COLUMN {table_name}.{column_name} IS '{comment}'")


def upgrade() -> None:
    op.create_table(
        "youtube_videos",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("youtube_video_id", sa.String(64), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("channel_name", sa.Text()),
        sa.Column("channel_url", sa.Text()),
        sa.Column("thumbnail_url", sa.Text()),
        sa.Column("duration_text", sa.String(64)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("published_text", sa.String(128)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("view_count_text", sa.String(128)),
        sa.Column("view_count", sa.BigInteger()),
        sa.Column("description", sa.Text()),
        sa.Column(
            "first_discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0"),
        sa.CheckConstraint("view_count IS NULL OR view_count >= 0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("youtube_video_id"),
    )
    op.create_table(
        "search_queries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("query", sa.String(200), nullable=False),
        sa.Column("locale", sa.String(20), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column(
            "searched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("requested_limit > 0"),
        sa.CheckConstraint("result_count >= 0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_search_queries_query_searched_at",
        "search_queries",
        ["query", "searched_at"],
    )
    op.create_table(
        "transcripts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("source_language", sa.String(32)),
        sa.Column("source", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("object_name", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("segment_count", sa.Integer()),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
        sa.Column("stored_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','stored','unavailable','failed')",
            name="ck_transcripts_status",
        ),
        sa.CheckConstraint("segment_count IS NULL OR segment_count >= 0"),
        sa.CheckConstraint("attempt_count >= 0"),
        sa.ForeignKeyConstraint(
            ["video_id"], ["youtube_videos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "video_id", "language", name="uq_transcripts_video_language"
        ),
    )
    op.create_index("ix_transcripts_status", "transcripts", ["status"])
    op.create_table(
        "search_query_results",
        sa.Column("search_query_id", sa.BigInteger(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0"),
        sa.ForeignKeyConstraint(
            ["search_query_id"], ["search_queries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["youtube_videos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("search_query_id", "video_id"),
        sa.UniqueConstraint(
            "search_query_id", "position", name="uq_search_result_position"
        ),
    )
    op.create_index(
        "ix_search_query_results_video_id", "search_query_results", ["video_id"]
    )
    op.create_table(
        "search_index_jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("transcript_id", sa.BigInteger(), nullable=False),
        sa.Column("index_alias", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("generation_id", sa.String(64)),
        sa.Column("chunk_count", sa.Integer()),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','queued','running','indexed','failed')",
            name="ck_search_index_jobs_status",
        ),
        sa.CheckConstraint("chunk_count IS NULL OR chunk_count >= 0"),
        sa.CheckConstraint("attempt_count >= 0"),
        sa.ForeignKeyConstraint(
            ["transcript_id"], ["transcripts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transcript_id", "index_alias", name="uq_search_index_job_target"
        ),
    )
    op.create_index("ix_search_index_jobs_status", "search_index_jobs", ["status"])
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(128), nullable=False),
        sa.Column("deduplication_key", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','publishing','published','failed')",
            name="ck_outbox_events_status",
        ),
        sa.CheckConstraint("attempt_count >= 0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deduplication_key"),
    )
    op.create_index(
        "ix_outbox_events_dispatch", "outbox_events", ["status", "available_at"]
    )
    _add_database_comments()


def downgrade() -> None:
    op.drop_index("ix_outbox_events_dispatch", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_search_index_jobs_status", table_name="search_index_jobs")
    op.drop_table("search_index_jobs")
    op.drop_index("ix_search_query_results_video_id", table_name="search_query_results")
    op.drop_table("search_query_results")
    op.drop_index("ix_transcripts_status", table_name="transcripts")
    op.drop_table("transcripts")
    op.drop_index("ix_search_queries_query_searched_at", table_name="search_queries")
    op.drop_table("search_queries")
    op.drop_table("youtube_videos")
