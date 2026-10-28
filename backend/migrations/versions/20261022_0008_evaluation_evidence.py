"""Store verifiable, per-dimension score evidence.

Revision ID: 20261022_0008
Revises: 20261022_0007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261022_0008"
down_revision: Union[str, None] = "20261022_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_id", sa.String(length=36), nullable=False),
        sa.Column("dimension", sa.String(length=20), nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False),
        sa.Column("question_message_id", sa.String(length=36), nullable=False),
        sa.Column("answer_message_id", sa.String(length=36), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("resume_quote", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", "dimension"),
    )
    op.create_index("ix_evaluation_evidence_evaluation_id", "evaluation_evidence", ["evaluation_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_evidence_evaluation_id", table_name="evaluation_evidence")
    op.drop_table("evaluation_evidence")
