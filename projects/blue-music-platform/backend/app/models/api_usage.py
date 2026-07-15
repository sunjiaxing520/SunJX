from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApiUsageRecord(Base):
    __tablename__ = "api_usage_records"
    __table_args__ = (
        Index("ix_api_usage_task", "task_type", "task_id"),
        Index("ix_api_usage_provider_created", "provider", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    is_external: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    external_request_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    cached_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    usage_unit: Mapped[str] = mapped_column(
        String(30), default="tokens", server_default="tokens", nullable=False
    )
    usage_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0"), server_default="0", nullable=False
    )
    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
