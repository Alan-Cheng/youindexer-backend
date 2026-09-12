"""Transcript lifecycle and MinIO asset models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

if TYPE_CHECKING:
    from app.database.models.indexing import SearchIndexJob
    from app.database.models.youtube import YouTubeVideo


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True, comment="字幕紀錄識別碼"
    )
    video_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("youtube_videos.id", ondelete="CASCADE"),
        comment="YouTube 影片內部識別碼",
    )
    language: Mapped[str] = mapped_column(String(20), comment="字幕目標語言")
    source_language: Mapped[str | None] = mapped_column(
        String(32), comment="字幕原始語言"
    )
    source: Mapped[str | None] = mapped_column(String(64), comment="字幕來源類型")
    status: Mapped[str] = mapped_column(
        String(32), default="pending", comment="字幕處理狀態"
    )
    object_name: Mapped[str | None] = mapped_column(Text, comment="MinIO 字幕物件路徑")
    content_hash: Mapped[str | None] = mapped_column(
        String(64), comment="字幕內容 SHA-256"
    )
    segment_count: Mapped[int | None] = mapped_column(Integer, comment="字幕片段數")
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="字幕處理嘗試次數"
    )
    last_error: Mapped[str | None] = mapped_column(Text, comment="最近一次錯誤訊息")
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="字幕自來源取得時間"
    )
    stored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="字幕寫入 MinIO 時間"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="資料建立時間"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="資料更新時間",
    )

    video: Mapped[YouTubeVideo] = relationship(back_populates="transcripts")
    index_jobs: Mapped[list[SearchIndexJob]] = relationship(
        back_populates="transcript", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("video_id", "language", name="uq_transcripts_video_language"),
        CheckConstraint(
            "status IN ('pending','running','stored','unavailable','failed')",
            name="ck_transcripts_status",
        ),
        CheckConstraint("segment_count IS NULL OR segment_count >= 0"),
        CheckConstraint("attempt_count >= 0"),
        Index("ix_transcripts_status", "status"),
        {"comment": "每支影片各語言字幕的處理狀態與 MinIO 位置"},
    )
