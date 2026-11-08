"""training session language

Revision ID: 20261108_0041
Revises: 20261108_0040
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261108_0041"
down_revision: str | None = "20261108_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.add_column(
            sa.Column("language", sa.String(length=8), nullable=False, server_default="zh")
        )


def downgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.drop_column("language")
