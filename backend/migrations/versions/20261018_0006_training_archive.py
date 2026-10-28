"""Add reversible session archive state.

Revision ID: 20261018_0006
Revises: 20261018_0005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261018_0006"
down_revision: Union[str, None] = "20261018_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_training_sessions_archived_at", ["archived_at"])


def downgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch_op:
        batch_op.drop_index("ix_training_sessions_archived_at")
        batch_op.drop_column("archived_at")
