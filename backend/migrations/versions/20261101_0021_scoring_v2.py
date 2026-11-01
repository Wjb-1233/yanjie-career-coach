"""add reference text and stability

Revision ID: 20261101_0021
Revises: 20261101_0020
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_0021"
down_revision: Union[str, None] = "20261101_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.add_column(sa.Column("reference_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("stability", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.drop_column("stability")
        batch.drop_column("reference_text")
