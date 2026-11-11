"""share revocations

Revision ID: 20261109_0044
Revises: 20261108_0043
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261109_0044"
down_revision: str | None = "20261108_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "share_revocations",
        sa.Column("token_sig", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("token_sig"),
    )
    op.create_index("ix_share_revocations_session_id", "share_revocations", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_share_revocations_session_id", table_name="share_revocations")
    op.drop_table("share_revocations")
