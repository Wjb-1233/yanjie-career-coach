"""Persist coaching highlights with each script version.

Revision ID: 20261018_0005
Revises: 20261018_0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261018_0005"
down_revision: Union[str, None] = "20261018_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("scripts") as batch_op:
        batch_op.add_column(sa.Column("highlights", sa.JSON(), nullable=True))
    op.execute(sa.text("UPDATE scripts SET highlights = '[]' WHERE highlights IS NULL"))
    with op.batch_alter_table("scripts") as batch_op:
        batch_op.alter_column("highlights", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("scripts") as batch_op:
        batch_op.drop_column("highlights")
