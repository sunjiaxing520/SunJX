from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReviewAgent(Base):
    __tablename__ = "review_agents"
    __table_args__ = (
        CheckConstraint(
            "pass_score >= 1 AND pass_score <= 100",
            name="ck_review_agents_pass_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    pass_score: Mapped[int] = mapped_column(
        Integer,
        default=80,
        server_default="80",
        nullable=False,
    )
    initialization_notes: Mapped[str] = mapped_column(Text, nullable=False)
    memory_summary: Mapped[str] = mapped_column(Text, nullable=False)
    memory_detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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
    members: Mapped[list["ReviewAgentMember"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reviews: Mapped[list["ReviewRun"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ReviewAgentMember(Base):
    __tablename__ = "review_agent_members"

    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("review_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agent: Mapped[ReviewAgent] = relationship(back_populates="members")


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("review_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lyrics_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lyrics_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agent: Mapped[ReviewAgent] = relationship(back_populates="reviews")
