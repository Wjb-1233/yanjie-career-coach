"""add session mode

Revision ID: 20261103_0030
Revises: 20261103_0029
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_0030"
down_revision: Union[str, None] = "20261103_0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.add_column(sa.Column("mode", sa.String(12), nullable=False, server_default="STANDARD"))


def downgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.drop_column("mode")
