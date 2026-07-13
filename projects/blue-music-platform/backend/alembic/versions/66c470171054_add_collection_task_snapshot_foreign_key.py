"""add collection task snapshot foreign key

Revision ID: 66c470171054
Revises: d46f1588ed37
Create Date: 2026-07-13 19:23:27.890869

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '66c470171054'
down_revision: Union[str, None] = 'd46f1588ed37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_collection_tasks_snapshot_id",
        "collection_tasks",
        "ranking_snapshots",
        ["snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_collection_tasks_snapshot_id",
        "collection_tasks",
        type_="foreignkey",
    )
