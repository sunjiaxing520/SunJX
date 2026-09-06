"""Consolidate lyrics learning into one shared team memory.

Revision ID: b6e4c8a2d710
Revises: c9b5d7e2a410
"""

from alembic import op
import sqlalchemy as sa


revision = "b6e4c8a2d710"
down_revision = "c9b5d7e2a410"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lyrics_team_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column(
            "injection_limit",
            sa.Integer(),
            server_default=sa.text("60"),
            nullable=False,
        ),
        sa.Column(
            "source_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "lyrics_versions",
        sa.Column("memory_committed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lyrics_versions", "memory_committed_at")
    op.drop_table("lyrics_team_memory")
