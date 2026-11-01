"""add skill states and mistake scheduling

Revision ID: 20261101_0022
Revises: 20261101_0021
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_0022"
down_revision: Union[str, None] = "20261101_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skill_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False, server_default="1000"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "dimension", name="uq_skill_user_dimension"),
    )
    op.create_index("ix_skill_states_user_id", "skill_states", ["user_id"])
    op.create_index("ix_skill_states_dimension", "skill_states", ["dimension"])

    with op.batch_alter_table("mistake_states") as batch:
        batch.add_column(sa.Column("streak", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_mistake_states_due_at", ["due_at"])


def downgrade() -> None:
    with op.batch_alter_table("mistake_states") as batch:
        batch.drop_index("ix_mistake_states_due_at")
        batch.drop_column("due_at")
        batch.drop_column("streak")
    op.drop_index("ix_skill_states_dimension", table_name="skill_states")
    op.drop_index("ix_skill_states_user_id", table_name="skill_states")
    op.drop_table("skill_states")
