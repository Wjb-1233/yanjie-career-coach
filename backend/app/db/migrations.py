from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import engine


BACKEND_ROOT = Path(__file__).resolve().parents[2]


async def assert_database_is_current() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    try:
        async with engine.connect() as connection:
            current = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "数据库尚未完成迁移，请先在 backend 目录运行：alembic upgrade head"
        ) from exc
    if current not in expected_heads:
        raise RuntimeError(
            f"数据库迁移版本落后（current={current!r}, expected={sorted(expected_heads)}），"
            "请先运行：alembic upgrade head"
        )
