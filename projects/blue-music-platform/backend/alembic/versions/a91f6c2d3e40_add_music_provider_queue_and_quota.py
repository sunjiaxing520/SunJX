"""add music provider queue and quota

Revision ID: a91f6c2d3e40
Revises: f31a8c72d604
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a91f6c2d3e40"
down_revision: Union[str, None] = "f31a8c72d604"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "music_tasks",
        sa.Column(
            "provider_implementation",
            sa.String(length=30),
            server_default="official",
            nullable=False,
        ),
    )
    op.add_column(
        "music_tasks",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "music_tasks",
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
    )
    op.add_column(
        "music_tasks",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "music_tasks",
        sa.Column("last_queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_music_tasks_next_attempt_at",
        "music_tasks",
        ["next_attempt_at"],
    )
    op.add_column(
        "music_results",
        sa.Column(
            "storage_backend",
            sa.String(length=20),
            server_default="local",
            nullable=False,
        ),
    )

    op.create_table(
        "music_provider_quota_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=50),
            server_default="suno",
            nullable=False,
        ),
        sa.Column(
            "provider_implementation",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("credits_remaining", sa.Float(), nullable=True),
        sa.Column("usage", sa.Float(), nullable=True),
        sa.Column("quota_limit", sa.Float(), nullable=True),
        sa.Column("period", sa.String(length=40), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_usage", sa.JSON(), nullable=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_music_provider_quota_snapshots_provider_implementation",
        "music_provider_quota_snapshots",
        ["provider_implementation"],
    )
    op.create_index(
        "ix_music_provider_quota_snapshots_checked_at",
        "music_provider_quota_snapshots",
        ["checked_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_music_provider_quota_snapshots_checked_at",
        table_name="music_provider_quota_snapshots",
    )
    op.drop_index(
        "ix_music_provider_quota_snapshots_provider_implementation",
        table_name="music_provider_quota_snapshots",
    )
    op.drop_table("music_provider_quota_snapshots")
    op.drop_column("music_results", "storage_backend")
    op.drop_index("ix_music_tasks_next_attempt_at", table_name="music_tasks")
    op.drop_column("music_tasks", "last_queued_at")
    op.drop_column("music_tasks", "next_attempt_at")
    op.drop_column("music_tasks", "max_attempts")
    op.drop_column("music_tasks", "attempt_count")
    op.drop_column("music_tasks", "provider_implementation")
