"""Make the complete test suite independent from developer and production data."""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest


TEST_DATABASE = Path(tempfile.gettempdir()) / f"career-coach-pytest-{uuid4().hex}.db"

# conftest is loaded before test modules, so application settings are created only
# after these deterministic, offline test values are installed.
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{TEST_DATABASE.as_posix()}",
        "AUTO_CREATE_SCHEMA": "true",
        "REDIS_ENABLED": "false",
        "MILVUS_ENABLED": "false",
        "LLM_API_KEY": "",
        "JWT_SECRET": "isolated-test-secret-longer-than-32-characters",
        "CORS_ORIGINS": "http://testserver",
    }
)


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database() -> Iterator[Path]:
    """Remove the temporary database after all app lifespans have completed."""

    yield TEST_DATABASE

    from app.db.base import engine

    asyncio.run(engine.dispose())
    for suffix in ("", "-journal", "-shm", "-wal"):
        Path(f"{TEST_DATABASE}{suffix}").unlink(missing_ok=True)
