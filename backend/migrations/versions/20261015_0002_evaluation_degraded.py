"""Persist whether an evaluation used local scoring rules.

Revision ID: 20261015_0002
Revises: 20261009_0001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261015_0002"
down_revision: Union[str, None] = "20261009_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FALLBACK_SUMMARY = "表达基本完成了沟通目标。下一步应让结论更靠前，并用可验证事实支撑关键判断。"


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.add_column(
            sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.get_bind().execute(
        sa.text("UPDATE evaluations SET degraded = :degraded WHERE summary = :summary"),
        {"degraded": True, "summary": FALLBACK_SUMMARY},
    )


def downgrade() -> None:
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.drop_column("degraded")
