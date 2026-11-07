"""add user owned scenes

Revision ID: 20261106_0033
Revises: 20261105_0032
Create Date: 2026-11-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_0033"
down_revision: Union[str, None] = "20261105_0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("scenes") as batch:
        batch.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("visibility", sa.String(16), nullable=False, server_default="public"))
        batch.add_column(sa.Column("source", sa.String(16), nullable=False, server_default="builtin"))
        batch.add_column(sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"))
        batch.create_index("ix_scenes_owner_id", ["owner_id"])
        batch.create_index("ix_scenes_visibility", ["visibility"])


def downgrade() -> None:
    with op.batch_alter_table("scenes") as batch:
        batch.drop_index("ix_scenes_visibility")
        batch.drop_index("ix_scenes_owner_id")
        batch.drop_column("usage_count")
        batch.drop_column("source")
        batch.drop_column("visibility")
        batch.drop_column("owner_id")
