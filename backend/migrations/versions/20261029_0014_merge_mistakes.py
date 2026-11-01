"""merge mistakes into script studio

Revision ID: 20261029_0014
Revises: 20261029_0013
Create Date: 2026-10-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0014"
down_revision: Union[str, None] = "20261029_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scripts", sa.Column("dimension", sa.String(20), nullable=True))
    op.add_column("scripts", sa.Column("source_session_id", sa.String(36), nullable=True))
    op.add_column("scripts", sa.Column("source_round", sa.Integer(), nullable=True))
    op.create_index("ix_scripts_source_session_id", "scripts", ["source_session_id"])
    op.create_table(
        "mistake_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "session_id", "round_no", "dimension", name="uq_mistake_state"),
    )
    op.create_index("ix_mistake_states_user_id", "mistake_states", ["user_id"])
    op.create_index("ix_mistake_states_session_id", "mistake_states", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_mistake_states_session_id", table_name="mistake_states")
    op.drop_index("ix_mistake_states_user_id", table_name="mistake_states")
    op.drop_table("mistake_states")
    op.drop_index("ix_scripts_source_session_id", table_name="scripts")
    op.drop_column("scripts", "source_round")
    op.drop_column("scripts", "source_session_id")
    op.drop_column("scripts", "dimension")
