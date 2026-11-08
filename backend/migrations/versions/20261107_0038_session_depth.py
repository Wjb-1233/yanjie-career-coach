"""training session depth

Revision ID: 20261107_0038
Revises: 20261107_0037
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261107_0038"
down_revision: str | None = "20261107_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.add_column(
            sa.Column("depth", sa.String(length=16), nullable=False, server_default="STANDARD")
        )


def downgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.drop_column("depth")
