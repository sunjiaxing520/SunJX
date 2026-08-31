"""add lyrics memory chat and snapshots

Revision ID: f3c7a2d5e860
Revises: e1b6c3d9f240
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3c7a2d5e860"
down_revision: Union[str, None] = "e1b6c3d9f240"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lyrics_memory_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("memory", sa.JSON(), nullable=False),
        sa.Column("source_event_count", sa.Integer(), nullable=False),
        sa.Column("capsule_char_count", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "lyrics_memory_chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=True),
        sa.Column(
            "is_applied",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lyrics_memory_chat_messages_role"),
        "lyrics_memory_chat_messages",
        ["role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_lyrics_memory_chat_messages_role"),
        table_name="lyrics_memory_chat_messages",
    )
    op.drop_table("lyrics_memory_chat_messages")
    op.drop_table("lyrics_memory_snapshots")
