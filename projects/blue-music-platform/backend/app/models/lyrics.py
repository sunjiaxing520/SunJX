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


class LyricsTask(Base):
    __tablename__ = "lyrics_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(20), default=TaskStatus.PENDING.value, nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requested_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    analysis_report_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("analysis_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    direction_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title_hint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    theme: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(
        String(30), default="中文", server_default="中文", nullable=False
    )
    genre_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    mood_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    scene_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    tempo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vocal_gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vocal_style: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    versions: Mapped[list["LyricsVersion"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LyricsVersion.version_number",
    )


class LyricsVersion(Base):
    __tablename__ = "lyrics_versions"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "version_number", name="uq_lyrics_task_version"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lyrics_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    style_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    is_saved: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    task: Mapped[LyricsTask] = relationship(back_populates="versions")
