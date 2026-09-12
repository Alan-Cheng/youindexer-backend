"""YouTube-specific video metadata models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

if TYPE_CHECKING:
    from app.database.models.transcription import Transcript


class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True, comment="影片內部識別碼"
    )
    youtube_video_id: Mapped[str] = mapped_column(
        String(64), unique=True, comment="YouTube 影片識別碼"
    )
    canonical_url: Mapped[str] = mapped_column(Text, comment="影片標準網址")
    title: Mapped[str] = mapped_column(Text, comment="影片標題")
    channel_name: Mapped[str | None] = mapped_column(Text, comment="頻道名稱")
    channel_url: Mapped[str | None] = mapped_column(Text, comment="頻道網址")
    thumbnail_url: Mapped[str | None] = mapped_column(Text, comment="縮圖網址")
    duration_text: Mapped[str | None] = mapped_column(
        String(64), comment="搜尋頁顯示的影片長度文字"
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer, comment="正規化後的影片長度秒數"
    )
    published_text: Mapped[str | None] = mapped_column(
        String(128), comment="搜尋頁顯示的發布時間文字"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="正規化後的影片發布時間"
    )
    view_count_text: Mapped[str | None] = mapped_column(
        String(128), comment="搜尋頁顯示的觀看次數文字"
    )
    view_count: Mapped[int | None] = mapped_column(
        BigInteger, comment="正規化後的觀看次數"
    )
    description: Mapped[str | None] = mapped_column(Text, comment="影片描述摘要")
    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="首次被搜尋發現時間"
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="最近一次出現在搜尋結果的時間",
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

    transcripts: Mapped[list[Transcript]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0"),
        CheckConstraint("view_count IS NULL OR view_count >= 0"),
        {"comment": "YouTube 影片主檔與搜尋取得的 metadata"},
    )
