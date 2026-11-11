from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine_options: dict[str, object] = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    engine_options.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
    )

engine = create_async_engine(settings.database_url, **engine_options)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
        """SQLite 默认不校验外键：模型里 27 个 ondelete=CASCADE 只在 MySQL 上生效。"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session



async def warmup_pool() -> None:
    """预热连接池，避免首批并发请求分担建连耗时。"""
    if settings.database_url.startswith("sqlite"):
        return
    connections = []
    try:
        for _ in range(max(1, settings.db_pool_size)):
            connections.append(await engine.connect())
    except Exception:  # noqa: BLE001 - 预热失败不影响启动
        pass
    finally:
        for connection in connections:
            await connection.close()
