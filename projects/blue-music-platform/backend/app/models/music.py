from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.workflow import TaskStatus


class MusicTask(Base):
    __tablename__ = "music_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(20), default=TaskStatus.PENDING.value, nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(
        String(20), default="generate", server_default="generate", nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(50), default="suno", server_default="suno", nullable=False
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requested_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    lyrics_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lyrics_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_result_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("music_results.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    lyrics: Mapped[str] = mapped_column(Text, nullable=False)
    style_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    instrumental: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    negative_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_task_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True, index=True
    )
    provider_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    results: Mapped[list["MusicResult"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="MusicResult.task_id",
        order_by="MusicResult.id",
    )


class MusicResult(Base):
    __tablename__ = "music_results"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "external_id", name="uq_music_result_external_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("music_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_type: Mapped[str] = mapped_column(
        String(100), default="audio/mpeg", server_default="audio/mpeg", nullable=False
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    task: Mapped[MusicTask] = relationship(
        back_populates="results", foreign_keys=[task_id]
    )
