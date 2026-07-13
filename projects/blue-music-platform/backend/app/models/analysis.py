from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.workflow import TaskStatus


class AnalysisTaskEntry(Base):
    __tablename__ = "analysis_task_entries"

    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("analysis_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entry_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ranking_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(20), default=TaskStatus.PENDING.value, nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    requested_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    selected_entries: Mapped[list[AnalysisTaskEntry]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    report: Mapped["AnalysisReport | None"] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("analysis_tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    trend_summary: Mapped[str] = mapped_column(Text, nullable=False)
    trend_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    creation_directions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    task: Mapped[AnalysisTask] = relationship(back_populates="report")
