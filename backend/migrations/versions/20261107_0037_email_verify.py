"""add email verification

Revision ID: 20261107_0037
Revises: 20261107_0036
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261107_0037"
down_revision: Union[str, None] = "20261107_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    # 老用户默认视为已验证，避免升级后集体被锁
    op.execute("UPDATE users SET email_verified = 1 WHERE email_verified IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified")
