"""question bank states

Revision ID: 20261107_0039
Revises: 20261107_0038
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261107_0039"
down_revision: str | None = "20261107_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

def downgrade() -> None:
    op.drop_table("question_bank_states")
