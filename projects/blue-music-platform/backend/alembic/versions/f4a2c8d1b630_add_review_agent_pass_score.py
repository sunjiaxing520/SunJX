"""add review agent pass score

Revision ID: f4a2c8d1b630
Revises: e3f1b7c9a420
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a2c8d1b630"
down_revision: Union[str, None] = "e3f1b7c9a420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "review_agents",
        sa.Column(
            "pass_score",
            sa.Integer(),
            server_default="80",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_review_agents_pass_score_range",
        "review_agents",
        "pass_score >= 1 AND pass_score <= 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_review_agents_pass_score_range",
        "review_agents",
        type_="check",
    )
    op.drop_column("review_agents", "pass_score")
