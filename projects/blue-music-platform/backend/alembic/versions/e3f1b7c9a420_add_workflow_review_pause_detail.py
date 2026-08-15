"""add workflow review pause detail

Revision ID: e3f1b7c9a420
Revises: d8a4c1b9e530
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f1b7c9a420"
down_revision: Union[str, None] = "d8a4c1b9e530"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_run_steps",
        sa.Column("result_detail", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_run_steps", "result_detail")
