"""add scene competency

Revision ID: 20261105_0032
Revises: 20261104_0031
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261105_0032"
down_revision: Union[str, None] = "20261104_0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 分类 → 岗位能力，用于把题库挂到能力模型上
CATEGORY_COMPETENCY = {
    "HR 初面": "求职动机与稳定性",
    "HRBP/HR 终面": "求职动机与稳定性",
    "技术一面": "技术深度",
    "技术二面/复面": "技术深度",
    "交叉面/总监面": "协作与影响力",
    "大老板/高管终面": "协作与影响力",
    "基础能力提升": "表达基本功",
}


def upgrade() -> None:
    with op.batch_alter_table("scenes") as batch:
        batch.add_column(sa.Column("competency", sa.String(30), nullable=True))
        batch.create_index("ix_scenes_competency", ["competency"])

    connection = op.get_bind()
    for category, competency in CATEGORY_COMPETENCY.items():
        connection.execute(
            sa.text("UPDATE scenes SET competency = :c WHERE category = :cat AND competency IS NULL"),
            {"c": competency, "cat": category},
        )
    connection.execute(sa.text("UPDATE scenes SET competency = '沟通表达' WHERE competency IS NULL"))


def downgrade() -> None:
    with op.batch_alter_table("scenes") as batch:
        batch.drop_index("ix_scenes_competency")
        batch.drop_column("competency")
