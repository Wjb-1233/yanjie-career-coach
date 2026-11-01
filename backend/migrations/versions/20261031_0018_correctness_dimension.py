"""rename impact dimension to correctness

Revision ID: 20261031_0018
Revises: 20261030_0017
Create Date: 2026-10-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261031_0018"
down_revision: Union[str, None] = "20261029_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.alter_column(
            "impact_score",
            new_column_name="correctness_score",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    op.execute("UPDATE evaluation_evidence SET dimension = 'correctness' WHERE dimension = 'impact'")
    op.execute("UPDATE mistake_states SET dimension = '正确性' WHERE dimension = '感染力'")
    op.execute("UPDATE courses SET dimension = '正确性' WHERE dimension = '感染力'")
    op.execute(
        "UPDATE courses SET title = '把信息说准确',"
        " description = '核对事实与口径，让每个数字和结论都经得起追问。',"
        " content = '先确认信息口径；说明数据来源；与简历保持一致；不确定的部分坦白说明。'"
        " WHERE id = 'course-impact-01'"
    )
    op.execute(
        "UPDATE scenes SET title = '把信息说准确',"
        " goal = '说清信息的事实依据与统计口径，与简历保持一致，不虚构、不含糊。',"
        " background = '面试官追问你简历里的一个数字，你要在不夸大的前提下说明它的来源和口径。',"
        " opening_line = '你简历里写的结果是怎么统计出来的？请说明口径和依据。'"
        " WHERE id = 'scene-foundation-impact'"
    )


def downgrade() -> None:
    op.execute("UPDATE evaluation_evidence SET dimension = 'impact' WHERE dimension = 'correctness'")
    op.execute("UPDATE mistake_states SET dimension = '感染力' WHERE dimension = '正确性'")
    op.execute("UPDATE courses SET dimension = '感染力' WHERE dimension = '正确性'")

    with op.batch_alter_table("evaluations") as batch:
        batch.alter_column(
            "correctness_score",
            new_column_name="impact_score",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
