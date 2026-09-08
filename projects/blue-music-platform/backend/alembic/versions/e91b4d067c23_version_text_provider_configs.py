"""Bind connection tests to a text provider configuration revision."""

from alembic import op
import sqlalchemy as sa

revision = "e91b4d067c23"
down_revision = "d82a5f904e16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_provider_configs", sa.Column(
        "config_revision", sa.Integer(), server_default="1", nullable=False,
    ))


def downgrade() -> None:
    op.drop_column("ai_provider_configs", "config_revision")
