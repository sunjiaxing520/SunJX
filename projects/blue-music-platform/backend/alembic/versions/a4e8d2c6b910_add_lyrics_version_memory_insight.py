"""add lyrics version memory insight

Revision ID: a4e8d2c6b910
Revises: f3c7a2d5e860
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4e8d2c6b910"
down_revision: Union[str, None] = "f3c7a2d5e860"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lyrics_versions",
        sa.Column("memory_insight", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lyrics_versions", "memory_insight")
