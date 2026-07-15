"""add favorite items

Revision ID: 9c32ab45f1d0
Revises: 7aeccccec7f8
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c32ab45f1d0"
down_revision: Union[str, None] = "7aeccccec7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "favorite_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_type", "target_id", name="uq_favorite_item_target"),
    )
    op.create_index(
        "ix_favorite_items_type_created",
        "favorite_items",
        ["item_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_favorite_items_type_created", table_name="favorite_items")
    op.drop_table("favorite_items")
