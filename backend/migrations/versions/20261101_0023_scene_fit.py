"""add scene fit weights

Revision ID: 20261101_0023
Revises: 20261101_0022
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_0023"
down_revision: Union[str, None] = "20261101_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("scenes") as batch:
        batch.add_column(sa.Column("scene_fit", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scenes") as batch:
        batch.drop_column("scene_fit")
