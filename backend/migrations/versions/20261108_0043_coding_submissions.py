"""coding submissions

Revision ID: 20261108_0043
Revises: 20261108_0042
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261108_0043"
down_revision: str | None = "20261108_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coding_submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=60), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coding_submissions_user_id", "coding_submissions", ["user_id"])
    op.create_index("ix_coding_submissions_problem_id", "coding_submissions", ["problem_id"])
    op.create_index("ix_coding_submissions_created_at", "coding_submissions", ["created_at"])


def downgrade() -> None:
    op.drop_table("coding_submissions")
