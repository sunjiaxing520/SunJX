"""add creative review and favorites

Revision ID: d8a4c1b9e530
Revises: b7d29e4f16c1
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8a4c1b9e530"
down_revision: Union[str, None] = "b7d29e4f16c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "favorite_items",
        sa.Column(
            "category",
            sa.String(length=20),
            server_default="unclassified",
            nullable=False,
        ),
    )
    op.create_index("ix_favorite_items_category", "favorite_items", ["category"])

    op.add_column(
        "music_tasks",
        sa.Column("style_tags", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column("music_tasks", sa.Column("adaptation_mode", sa.String(length=30), nullable=True))
    op.add_column("music_tasks", sa.Column("source_title", sa.String(length=200), nullable=True))
    op.add_column("music_tasks", sa.Column("source_artist", sa.String(length=200), nullable=True))
    op.add_column("music_tasks", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column(
        "music_tasks",
        sa.Column("rights_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("music_tasks", sa.Column("rights_note", sa.Text(), nullable=True))

    op.create_table(
        "music_provider_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("active_model", sa.String(length=100), server_default="v4.5", nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "lyrics_assistant_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("source_version_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("preview", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["lyrics_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_version_id"], ["lyrics_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lyrics_assistant_messages_task_id", "lyrics_assistant_messages", ["task_id"])
    op.create_index("ix_lyrics_assistant_messages_source_version_id", "lyrics_assistant_messages", ["source_version_id"])

    op.create_table(
        "review_agents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("initialization_notes", sa.Text(), nullable=False),
        sa.Column("memory_summary", sa.Text(), nullable=False),
        sa.Column("memory_detail", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "review_agent_members",
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["review_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "user_id"),
    )
    op.create_table(
        "review_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("lyrics_version_id", sa.Integer(), nullable=True),
        sa.Column("requested_by_id", sa.Integer(), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["review_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lyrics_version_id"], ["lyrics_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_runs_agent_id", "review_runs", ["agent_id"])
    op.create_index("ix_review_runs_lyrics_version_id", "review_runs", ["lyrics_version_id"])


def downgrade() -> None:
    op.drop_index("ix_review_runs_lyrics_version_id", table_name="review_runs")
    op.drop_index("ix_review_runs_agent_id", table_name="review_runs")
    op.drop_table("review_runs")
    op.drop_table("review_agent_members")
    op.drop_table("review_agents")
    op.drop_index("ix_lyrics_assistant_messages_source_version_id", table_name="lyrics_assistant_messages")
    op.drop_index("ix_lyrics_assistant_messages_task_id", table_name="lyrics_assistant_messages")
    op.drop_table("lyrics_assistant_messages")
    op.drop_table("music_provider_settings")
    op.drop_column("music_tasks", "rights_note")
    op.drop_column("music_tasks", "rights_confirmed")
    op.drop_column("music_tasks", "source_url")
    op.drop_column("music_tasks", "source_artist")
    op.drop_column("music_tasks", "source_title")
    op.drop_column("music_tasks", "adaptation_mode")
    op.drop_column("music_tasks", "style_tags")
    op.drop_index("ix_favorite_items_category", table_name="favorite_items")
    op.drop_column("favorite_items", "category")
