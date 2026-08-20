"""User and account models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Identity, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

if TYPE_CHECKING:
    from app.database.models.keyword_search import KeywordSearchJob


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True, comment="使用者識別碼"
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, comment="電子郵件"
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255), comment="顯示名稱"
    )
    google_subject: Mapped[str | None] = mapped_column(
        String(255), unique=True, comment="Google OAuth sub"
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

    search_jobs: Mapped[list[KeywordSearchJob]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_users_google_subject", "google_subject"),
        {"comment": "使用者帳號主檔"},
    )
