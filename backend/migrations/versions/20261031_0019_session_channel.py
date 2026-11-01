"""add session channel and duration

Revision ID: 20261031_0019
Revises: 20261031_0018
Create Date: 2026-10-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261031_0019"
down_revision: Union[str, None] = "20261031_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.add_column(sa.Column("channel", sa.String(10), nullable=False, server_default="TEXT"))
        batch.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=True))
        batch.create_index("ix_training_sessions_channel", ["channel"])


def downgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.drop_index("ix_training_sessions_channel")
        batch.drop_column("duration_seconds")
        batch.drop_column("channel")
