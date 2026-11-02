"""add analysis tasks

Revision ID: 20261102_0025
Revises: 20261102_0024
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0025"
down_revision: Union[str, None] = "20261102_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(60), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analysis_tasks_user_id", "analysis_tasks", ["user_id"])
    op.create_index("ix_analysis_tasks_kind", "analysis_tasks", ["kind"])
    op.create_index("ix_analysis_tasks_status", "analysis_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_analysis_tasks_status", table_name="analysis_tasks")
    op.drop_index("ix_analysis_tasks_kind", table_name="analysis_tasks")
    op.drop_index("ix_analysis_tasks_user_id", table_name="analysis_tasks")
    op.drop_table("analysis_tasks")
