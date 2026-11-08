"""group interviews

Revision ID: 20261108_0042
Revises: 20261108_0041
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261108_0042"
down_revision: str | None = "20261108_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_interviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("topic_id", sa.String(length=40), nullable=False),
        sa.Column("topic_title", sa.String(length=120), nullable=False),
        sa.Column("topic_prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("turns", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_group_interviews_user_id", "group_interviews", ["user_id"])
    op.create_index("ix_group_interviews_status", "group_interviews", ["status"])
    op.create_index("ix_group_interviews_created_at", "group_interviews", ["created_at"])


def downgrade() -> None:
    op.drop_table("group_interviews")
