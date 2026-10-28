"""Persist focused ability practice attempts.

Revision ID: 20261022_0009
Revises: 20261022_0008
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261022_0009"
down_revision: Union[str, None] = "20261022_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ability_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluation_id", sa.String(length=36), sa.ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension", sa.String(length=20), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("answer_quote", sa.Text(), nullable=False),
        sa.Column("strength", sa.Text(), nullable=False),
        sa.Column("gap", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ability_attempts_user_id", "ability_attempts", ["user_id"])
    op.create_index("ix_ability_attempts_evaluation_id", "ability_attempts", ["evaluation_id"])
    op.create_index("ix_ability_attempts_created_at", "ability_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ability_attempts_created_at", table_name="ability_attempts")
    op.drop_index("ix_ability_attempts_evaluation_id", table_name="ability_attempts")
    op.drop_index("ix_ability_attempts_user_id", table_name="ability_attempts")
    op.drop_table("ability_attempts")
