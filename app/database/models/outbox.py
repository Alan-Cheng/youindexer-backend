"""Transactional outbox models shared by worker domains."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True, comment="Outbox 事件識別碼"
    )
    event_type: Mapped[str] = mapped_column(String(128), comment="事件類型")
    aggregate_type: Mapped[str] = mapped_column(String(64), comment="事件主體類型")
    aggregate_id: Mapped[str] = mapped_column(String(128), comment="事件主體識別碼")
    deduplication_key: Mapped[str] = mapped_column(
        String(255), unique=True, comment="防止重複建立事件的唯一鍵"
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, comment="事件 JSON 內容")
    status: Mapped[str] = mapped_column(
        String(32), default="pending", comment="事件發布狀態"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="事件發布嘗試次數"
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="最早可發布時間"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="成功發布至訊息佇列時間"
    )
    last_error: Mapped[str | None] = mapped_column(Text, comment="最近一次發布錯誤")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="資料建立時間"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="資料更新時間",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','publishing','published','failed')",
            name="ck_outbox_events_status",
        ),
        CheckConstraint("attempt_count >= 0"),
        Index("ix_outbox_events_dispatch", "status", "available_at"),
        {"comment": "可靠發布 Celery 任務的 transactional outbox"},
    )
