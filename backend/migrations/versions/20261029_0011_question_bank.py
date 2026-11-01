"""scene question bank + session coverage

Revision ID: 20261029_0011
Revises: 20261029_0010
Create Date: 2026-10-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0011"
down_revision: Union[str, None] = "20261029_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scenes", sa.Column("question_bank", sa.JSON(), nullable=True))
    op.add_column(
        "training_sessions",
        sa.Column("covered_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("training_sessions", "covered_count")
    op.drop_column("scenes", "question_bank")
