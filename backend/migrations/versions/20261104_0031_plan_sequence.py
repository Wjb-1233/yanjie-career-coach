"""plan sequence and session plan link

Revision ID: 20261104_0031
Revises: 20261103_0030
Create Date: 2026-11-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_0031"
down_revision: Union[str, None] = "20261103_0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("training_plans") as batch:
        batch.add_column(sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"))
        batch.create_index("ix_training_plans_sequence", ["sequence"])

    with op.batch_alter_table("training_sessions") as batch:
        batch.add_column(sa.Column("plan_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("task_key", sa.String(20), nullable=True))
        batch.create_index("ix_training_sessions_plan_id", ["plan_id"])

    # 历史计划按创建时间给每位学员补序号
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, user_id FROM training_plans ORDER BY user_id, created_at")
    ).fetchall()
    counters: dict[str, int] = {}
    for plan_id, user_id in rows:
        counters[user_id] = counters.get(user_id, 0) + 1
        connection.execute(
            sa.text("UPDATE training_plans SET sequence = :seq WHERE id = :id"),
            {"seq": counters[user_id], "id": plan_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.drop_index("ix_training_sessions_plan_id")
        batch.drop_column("task_key")
        batch.drop_column("plan_id")

    with op.batch_alter_table("training_plans") as batch:
        batch.drop_index("ix_training_plans_sequence")
        batch.drop_column("sequence")
