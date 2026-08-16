"""add review scope to lyrics assistant

Revision ID: a6c9d2e4f810
Revises: f4a2c8d1b630
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c9d2e4f810"
down_revision: Union[str, None] = "f4a2c8d1b630"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lyrics_assistant_messages",
        sa.Column("review_run_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_lyrics_assistant_messages_review_run_id_review_runs",
        "lyrics_assistant_messages",
        "review_runs",
        ["review_run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_lyrics_assistant_messages_review_run_id",
        "lyrics_assistant_messages",
        ["review_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lyrics_assistant_messages_review_run_id",
        table_name="lyrics_assistant_messages",
    )
    op.drop_constraint(
        "fk_lyrics_assistant_messages_review_run_id_review_runs",
        "lyrics_assistant_messages",
        type_="foreignkey",
    )
    op.drop_column("lyrics_assistant_messages", "review_run_id")
