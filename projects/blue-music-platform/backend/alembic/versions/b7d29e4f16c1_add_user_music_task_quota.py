"""add user music task quota

Revision ID: b7d29e4f16c1
Revises: a91f6c2d3e40
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d29e4f16c1"
down_revision: Union[str, None] = "a91f6c2d3e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "music_quota_remaining",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "music_quota_used",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_music_quota_remaining_nonnegative",
        "users",
        "music_quota_remaining >= 0",
    )
    op.create_check_constraint(
        "ck_users_music_quota_used_nonnegative",
        "users",
        "music_quota_used >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_music_quota_used_nonnegative",
        "users",
        type_="check",
    )
    op.drop_constraint(
        "ck_users_music_quota_remaining_nonnegative",
        "users",
        type_="check",
    )
    op.drop_column("users", "music_quota_used")
    op.drop_column("users", "music_quota_remaining")
