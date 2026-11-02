"""add evaluation duration

Revision ID: 20261102_0026
Revises: 20261102_0025
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0026"
down_revision: Union[str, None] = "20261102_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.drop_column("duration_ms")
