"""Add interview industry and position metadata to scenario records.

Revision ID: 20261018_0003
Revises: 20261015_0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261018_0003"
down_revision: Union[str, None] = "20261015_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("scenes") as batch_op:
        batch_op.add_column(
            sa.Column("industry", sa.String(length=60), nullable=False, server_default="综合行业")
        )
        batch_op.add_column(
            sa.Column("position", sa.String(length=80), nullable=False, server_default="通用岗位")
        )


def downgrade() -> None:
    with op.batch_alter_table("scenes") as batch_op:
        batch_op.drop_column("position")
        batch_op.drop_column("industry")
