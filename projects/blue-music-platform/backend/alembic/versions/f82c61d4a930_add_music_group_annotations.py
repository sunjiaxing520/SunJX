"""Persist labels and notes for each music generation group."""
from alembic import op
import sqlalchemy as sa

revision = "f82c61d4a930"
down_revision = "e91b4d067c23"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("music_tasks", sa.Column("display_label", sa.String(80), nullable=True))
    op.add_column("music_tasks", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("music_tasks", sa.Column("is_marked", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    op.drop_column("music_tasks", "is_marked")
    op.drop_column("music_tasks", "note")
    op.drop_column("music_tasks", "display_label")
