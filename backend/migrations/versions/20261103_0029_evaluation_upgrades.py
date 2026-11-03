"""add evaluation upgrades

Revision ID: 20261103_0029
Revises: 20261103_0028
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_0029"
down_revision: Union[str, None] = "20261103_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.add_column(sa.Column("upgrades", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.drop_column("upgrades")
