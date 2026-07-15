from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AiProviderConfig(Base):
    __tablename__ = "ai_provider_configs"
    __table_args__ = (
        Index(
            "uq_ai_provider_configs_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    template_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hint: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    supports_json_mode: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    max_tokens_parameter: Mapped[str] = mapped_column(
        String(40), default="max_tokens", server_default="max_tokens", nullable=False
    )
    request_timeout_seconds: Mapped[float] = mapped_column(
        Float, default=60, server_default="60", nullable=False
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2", nullable=False
    )
    analysis_max_output_tokens: Mapped[int] = mapped_column(
        Integer, default=2500, server_default="2500", nullable=False
    )
    lyrics_max_output_tokens: Mapped[int] = mapped_column(
        Integer, default=3500, server_default="3500", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual", nullable=False
    )
    last_test_status: Mapped[str] = mapped_column(
        String(20), default="untested", server_default="untested", nullable=False
    )
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
