"""Search history and ranked result models."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

if TYPE_CHECKING:
    from app.database.models.youtube import YouTubeVideo


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True, comment="搜尋紀錄識別碼"
    )
    query: Mapped[str] = mapped_column(String(200), comment="使用者搜尋關鍵字")
    locale: Mapped[str] = mapped_column(String(20), comment="搜尋使用的語系")
    requested_limit: Mapped[int] = mapped_column(Integer, comment="要求的最大結果數")
    result_count: Mapped[int] = mapped_column(Integer, comment="實際取得的結果數")
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="執行搜尋時間"
    )

    results: Mapped[list[SearchQueryResult]] = relationship(
        back_populates="search_query", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("requested_limit > 0"),
        CheckConstraint("result_count >= 0"),
        Index("ix_search_queries_query_searched_at", "query", "searched_at"),
        {"comment": "YouTube 關鍵字搜尋歷史"},
    )


class SearchQueryResult(Base):
    __tablename__ = "search_query_results"

    search_query_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("search_queries.id", ondelete="CASCADE"),
        primary_key=True,
        comment="搜尋紀錄識別碼",
    )
    video_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("youtube_videos.id", ondelete="CASCADE"),
        primary_key=True,
        comment="影片識別碼",
    )
    position: Mapped[int] = mapped_column(Integer, comment="影片在該次搜尋結果的順位")

    search_query: Mapped[SearchQuery] = relationship(back_populates="results")
    video: Mapped[YouTubeVideo] = relationship()

    __table_args__ = (
        UniqueConstraint("search_query_id", "position", name="uq_search_result_position"),
        CheckConstraint("position >= 0"),
        Index("ix_search_query_results_video_id", "video_id"),
        {"comment": "每次搜尋所包含的影片及顯示順位"},
    )
