"""Runtime-adjustable system configuration model."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(
        String(255), primary_key=True, comment="設定項目名稱"
    )
    value: Mapped[Any] = mapped_column(JSON, nullable=False, comment="設定值（JSON 格式）")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="資料建立時間"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="資料更新時間",
    )

    __table_args__ = ({"comment": "系統可動態調整的設定參數"},)
