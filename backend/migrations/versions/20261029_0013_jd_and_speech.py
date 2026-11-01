"""session jd + question plan, evaluation speech stats

Revision ID: 20261029_0013
Revises: 20261029_0012
Create Date: 2026-10-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0013"
down_revision: Union[str, None] = "20261029_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("training_sessions", sa.Column("jd_text", sa.Text(), nullable=True))
    op.add_column("training_sessions", sa.Column("question_plan", sa.JSON(), nullable=True))
    op.add_column("evaluations", sa.Column("speech_stats", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluations", "speech_stats")
    op.drop_column("training_sessions", "question_plan")
    op.drop_column("training_sessions", "jd_text")
