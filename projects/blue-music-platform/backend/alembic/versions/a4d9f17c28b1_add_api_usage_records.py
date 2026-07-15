"""add api usage records

Revision ID: a4d9f17c28b1
Revises: 66c470171054
Create Date: 2026-07-15 11:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4d9f17c28b1"
down_revision: Union[str, None] = "66c470171054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_usage_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=30), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=60), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("method", sa.String(length=12), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("is_external", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("external_request_id", sa.String(length=200), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cached_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("usage_unit", sa.String(length=30), server_default="tokens", nullable=False),
        sa.Column("usage_quantity", sa.Numeric(precision=18, scale=6), server_default="0", nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=12), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_usage", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_usage_records_created_at", "api_usage_records", ["created_at"], unique=False)
    op.create_index("ix_api_usage_task", "api_usage_records", ["task_type", "task_id"], unique=False)
    op.create_index("ix_api_usage_provider_created", "api_usage_records", ["provider", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_usage_provider_created", table_name="api_usage_records")
    op.drop_index("ix_api_usage_task", table_name="api_usage_records")
    op.drop_index("ix_api_usage_records_created_at", table_name="api_usage_records")
    op.drop_table("api_usage_records")
