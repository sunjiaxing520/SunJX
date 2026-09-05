"""Persist the original input for two-mode lyrics composition.

Revision ID: c9b5d7e2a410
Revises: a4e8d2c6b910
"""
from alembic import op
import sqlalchemy as sa

revision = "c9b5d7e2a410"
down_revision = "a4e8d2c6b910"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lyrics_tasks", sa.Column("creation_input", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("lyrics_tasks", "creation_input")
