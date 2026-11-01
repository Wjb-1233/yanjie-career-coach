"""scene core idea

Revision ID: 20261029_0015
Revises: 20261029_0014
Create Date: 2026-10-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0015"
down_revision: Union[str, None] = "20261029_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scenes", sa.Column("core_idea", sa.Text(), nullable=True))
    op.execute("UPDATE scenes SET core_idea = goal WHERE core_idea IS NULL")


def downgrade() -> None:
    op.drop_column("scenes", "core_idea")
