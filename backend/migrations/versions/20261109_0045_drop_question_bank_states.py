"""drop question bank states

题库刷题功能已下线，relation 表随之移除；题库数据本身仍保存在
content/question-banks.json，训练流程照旧读取。

Revision ID: 20261109_0045
Revises: 20261109_0044
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261109_0045"
down_revision: str | None = "20261109_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("question_bank_states")


def downgrade() -> None:
    op.create_table(
        "question_bank_states",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=32), nullable=False),
        sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mastered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "question_id"),
    )
