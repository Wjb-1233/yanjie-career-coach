"""resume diagnoses

Revision ID: 20261108_0040
Revises: 20261107_0039
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261108_0040"
down_revision: str | None = "20261107_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resume_diagnoses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("jd_excerpt", sa.Text(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_diagnoses_user_id", "resume_diagnoses", ["user_id"])
    op.create_index("ix_resume_diagnoses_created_at", "resume_diagnoses", ["created_at"])


def downgrade() -> None:
    op.drop_table("resume_diagnoses")
