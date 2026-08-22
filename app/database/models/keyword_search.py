"""Persistent keyword-search jobs and per-video OpenSearch results."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.database.models.youtube import YouTubeVideo

if TYPE_CHECKING:
    from app.database.models.user import User


class KeywordSearchJob(Base):
    __tablename__ = "keyword_search_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="建立任務的使用者",
    )
    query: Mapped[str] = mapped_column(String(200))
    locale: Mapped[str] = mapped_column(String(20))
    requested_count: Mapped[int] = mapped_column(Integer)
    matches_per_video: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="processing")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User | None] = relationship(back_populates="search_jobs")
    videos: Mapped[list[KeywordSearchJobVideo]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("requested_count > 0"),
        CheckConstraint("matches_per_video > 0"),
        CheckConstraint("status IN ('processing','completed','failed')"),
        Index("ix_keyword_search_jobs_status", "status"),
        Index("ix_keyword_search_jobs_user_id", "user_id"),
    )


class KeywordSearchJobVideo(Base):
    __tablename__ = "keyword_search_job_videos"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("keyword_search_jobs.id", ondelete="CASCADE")
    )
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("youtube_videos.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="loading")
    keyword_matches: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[KeywordSearchJob] = relationship(back_populates="videos")
    video: Mapped[YouTubeVideo] = relationship()

    __table_args__ = (
        UniqueConstraint("job_id", "video_id"),
        UniqueConstraint("job_id", "position"),
        CheckConstraint("position >= 0"),
        CheckConstraint("status IN ('loading','matched','no_match','failed')"),
        Index("ix_keyword_search_job_videos_job_id", "job_id"),
    )
