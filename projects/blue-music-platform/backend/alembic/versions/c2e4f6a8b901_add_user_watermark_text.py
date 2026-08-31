"""add user watermark text

Revision ID: c2e4f6a8b901
Revises: a6c9d2e4f810
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2e4f6a8b901"
down_revision: Union[str, None] = "a6c9d2e4f810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("watermark_text", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "watermark_text")
