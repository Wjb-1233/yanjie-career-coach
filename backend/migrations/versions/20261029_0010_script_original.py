"""scripts.original

Revision ID: 20261029_0010
Revises: 20261022_0009
Create Date: 2026-10-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0010"
down_revision: Union[str, None] = "20261022_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scripts", sa.Column("original", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scripts", "original")
