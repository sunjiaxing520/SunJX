"""Snapshot the credential used by an asynchronous music task."""

from alembic import op
import sqlalchemy as sa


revision = "d82a5f904e16"
down_revision = "c4f8a1d2e630"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("music_tasks", sa.Column("provider_token_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("music_tasks", "provider_token_encrypted")
