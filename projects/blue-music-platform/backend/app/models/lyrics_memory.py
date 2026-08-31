from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LyricsMemoryEvent(Base):
    """Private evidence used to build the hidden lyric-writing memory capsule."""

    __tablename__ = "lyrics_memory_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    task_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lyrics_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lyrics_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dedupe_key: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True
    )
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_content: Mapped[str] = mapped_column(Text, nullable=False)
    context_data: Mapped[dict[str, Any]] = mapped_column(
        "context", JSON, nullable=False
    )
    is_useful: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
