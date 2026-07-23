"""add suno music tasks and results

Revision ID: f31a8c72d604
Revises: b7e2c8d4a901
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f31a8c72d604"
down_revision: Union[str, None] = "b7e2c8d4a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "music_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "operation",
            sa.String(length=20),
            server_default="generate",
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=50),
            server_default="suno",
            nullable=False,
        ),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("requested_by_id", sa.Integer(), nullable=True),
        sa.Column("lyrics_version_id", sa.Integer(), nullable=True),
        sa.Column("source_result_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("lyrics", sa.Text(), nullable=False),
        sa.Column("style_prompt", sa.Text(), nullable=False),
        sa.Column(
            "instrumental", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("negative_tags", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("external_task_id", sa.String(length=200), nullable=True),
        sa.Column("provider_status", sa.String(length=80), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["lyrics_version_id"], ["lyrics_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_music_tasks_status", "music_tasks", ["status"])
    op.create_index(
        "ix_music_tasks_lyrics_version_id", "music_tasks", ["lyrics_version_id"]
    )
    op.create_index(
        "ix_music_tasks_source_result_id", "music_tasks", ["source_result_id"]
    )
    op.create_index(
        "ix_music_tasks_external_task_id", "music_tasks", ["external_task_id"]
    )

    op.create_table(
        "music_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("audio_url", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column(
            "media_type",
            sa.String(length=100),
            server_default="audio/mpeg",
            nullable=False,
        ),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("provider_page_url", sa.Text(), nullable=True),
        sa.Column("storage_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["music_tasks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id", "external_id", name="uq_music_result_external_id"
        ),
    )
    op.create_index("ix_music_results_task_id", "music_results", ["task_id"])
    op.create_foreign_key(
        "fk_music_tasks_source_result_id",
        "music_tasks",
        "music_results",
        ["source_result_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_music_tasks_source_result_id", "music_tasks", type_="foreignkey"
    )
    op.drop_index("ix_music_results_task_id", table_name="music_results")
    op.drop_table("music_results")
    op.drop_index("ix_music_tasks_external_task_id", table_name="music_tasks")
    op.drop_index("ix_music_tasks_source_result_id", table_name="music_tasks")
    op.drop_index("ix_music_tasks_lyrics_version_id", table_name="music_tasks")
    op.drop_index("ix_music_tasks_status", table_name="music_tasks")
    op.drop_table("music_tasks")
