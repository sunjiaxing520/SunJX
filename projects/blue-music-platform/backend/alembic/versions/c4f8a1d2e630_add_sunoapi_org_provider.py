"""Add sunoapi.org provider configuration and callback state.

Revision ID: c4f8a1d2e630
Revises: b6e4c8a2d710
"""

from alembic import op
import sqlalchemy as sa


revision = "c4f8a1d2e630"
down_revision = "b6e4c8a2d710"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "music_tasks",
        sa.Column("provider_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "music_tasks",
        sa.Column("provider_callback_type", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "music_tasks",
        sa.Column(
            "provider_callback_received_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "music_provider_settings",
        sa.Column("active_implementation", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "music_provider_settings",
        sa.Column("sunoapi_org_token_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "music_provider_settings",
        sa.Column("sunoapi_org_token_hint", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "music_provider_settings",
        sa.Column("sunoapi_org_callback_base_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "music_provider_settings",
        sa.Column(
            "sunoapi_org_callback_secret_encrypted",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "music_provider_settings", "sunoapi_org_callback_secret_encrypted"
    )
    op.drop_column("music_provider_settings", "sunoapi_org_callback_base_url")
    op.drop_column("music_provider_settings", "sunoapi_org_token_hint")
    op.drop_column("music_provider_settings", "sunoapi_org_token_encrypted")
    op.drop_column("music_provider_settings", "active_implementation")
    op.drop_column("music_tasks", "provider_callback_received_at")
    op.drop_column("music_tasks", "provider_callback_type")
    op.drop_column("music_tasks", "provider_submitted_at")
