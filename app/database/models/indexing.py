"""OpenSearch indexing workflow models."""

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
    from app.database.models.transcription import Transcript


class SearchIndexJob(Base):
    __tablename__ = "search_index_jobs"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True, comment="索引工作識別碼"
    )
    transcript_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        comment="字幕紀錄識別碼",
    )
    index_alias: Mapped[str] = mapped_column(
        String(255), default="subtitle-segments", comment="OpenSearch 索引別名"
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", comment="索引工作狀態"
    )
    generation_id: Mapped[str | None] = mapped_column(
        String(64), comment="本次索引內容版本識別碼"
    )
    chunk_count: Mapped[int | None] = mapped_column(Integer, comment="已索引片段數")
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="索引嘗試次數"
    )
    last_error: Mapped[str | None] = mapped_column(Text, comment="最近一次錯誤訊息")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="最近一次開始索引時間"
    )
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="索引成功完成時間"
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

    transcript: Mapped[Transcript] = relationship(back_populates="index_jobs")

    __table_args__ = (
        UniqueConstraint(
            "transcript_id", "index_alias", name="uq_search_index_job_target"
        ),
        CheckConstraint(
            "status IN ('pending','queued','running','indexed','failed')",
            name="ck_search_index_jobs_status",
        ),
        CheckConstraint("chunk_count IS NULL OR chunk_count >= 0"),
        CheckConstraint("attempt_count >= 0"),
        Index("ix_search_index_jobs_status", "status"),
        {"comment": "字幕寫入 OpenSearch 的工作狀態"},
    )
