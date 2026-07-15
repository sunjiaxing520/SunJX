"""add ai provider configurations

Revision ID: 7aeccccec7f8
Revises: a4d9f17c28b1
Create Date: 2026-07-15 12:04:56.544358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7aeccccec7f8"
down_revision: Union[str, None] = "a4d9f17c28b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("template_key", sa.String(length=40), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False),
        sa.Column("base_url", sa.Text(), server_default="", nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("api_key_hint", sa.String(length=30), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("supports_json_mode", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("max_tokens_parameter", sa.String(length=40), server_default="max_tokens", nullable=False),
        sa.Column("request_timeout_seconds", sa.Float(), server_default="60", nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default="2", nullable=False),
        sa.Column("analysis_max_output_tokens", sa.Integer(), server_default="2500", nullable=False),
        sa.Column("lyrics_max_output_tokens", sa.Integer(), server_default="3500", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="manual", nullable=False),
        sa.Column("last_test_status", sa.String(length=20), server_default="untested", nullable=False),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_provider_configs_is_active", "ai_provider_configs", ["is_active"], unique=False)
    op.create_index("ix_ai_provider_configs_name", "ai_provider_configs", ["name"], unique=True)
    op.create_index("ix_ai_provider_configs_template_key", "ai_provider_configs", ["template_key"], unique=False)
    op.create_index(
        "uq_ai_provider_configs_active",
        "ai_provider_configs",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_ai_provider_configs_active", table_name="ai_provider_configs")
    op.drop_index("ix_ai_provider_configs_template_key", table_name="ai_provider_configs")
    op.drop_index("ix_ai_provider_configs_name", table_name="ai_provider_configs")
    op.drop_index("ix_ai_provider_configs_is_active", table_name="ai_provider_configs")
    op.drop_table("ai_provider_configs")
