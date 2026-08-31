"""add lyrics memory events

Revision ID: d8a4f1c7e920
Revises: c2e4f6a8b901
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8a4f1c7e920"
down_revision: Union[str, None] = "c2e4f6a8b901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lyrics_memory_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("source_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("cleaned_content", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column(
            "is_useful",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_version_id"], ["lyrics_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["lyrics_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        op.f("ix_lyrics_memory_events_created_by_id"),
        "lyrics_memory_events",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lyrics_memory_events_event_type"),
        "lyrics_memory_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lyrics_memory_events_is_useful"),
        "lyrics_memory_events",
        ["is_useful"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lyrics_memory_events_source_version_id"),
        "lyrics_memory_events",
        ["source_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lyrics_memory_events_task_id"),
        "lyrics_memory_events",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lyrics_memory_events_task_id"), table_name="lyrics_memory_events")
    op.drop_index(op.f("ix_lyrics_memory_events_source_version_id"), table_name="lyrics_memory_events")
    op.drop_index(op.f("ix_lyrics_memory_events_is_useful"), table_name="lyrics_memory_events")
    op.drop_index(op.f("ix_lyrics_memory_events_event_type"), table_name="lyrics_memory_events")
    op.drop_index(op.f("ix_lyrics_memory_events_created_by_id"), table_name="lyrics_memory_events")
    op.drop_table("lyrics_memory_events")
