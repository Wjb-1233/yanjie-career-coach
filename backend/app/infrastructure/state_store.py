import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings


class SessionStateStore:
    def __init__(self) -> None:
        self._memory: dict[str, dict[str, Any]] = {}
        redis_password = (
            settings.redis_password.get_secret_value() if settings.redis_password else None
        )
        self._redis = Redis.from_url(
            settings.redis_url,
            password=redis_password,
            decode_responses=True,
        )
        self._remote_available = False

    async def initialize(self) -> None:
        if not settings.redis_enabled:
            return
        try:
            await self._redis.ping()
            self._remote_available = True
        except Exception:
            self._remote_available = False

    async def set(self, session_id: str, state: dict[str, Any]) -> None:
        self._memory[session_id] = state
        if self._remote_available:
            try:
                await self._redis.setex(f"training:{session_id}", 7200, json.dumps(state, ensure_ascii=False))
            except Exception:
                self._remote_available = False

    async def get(self, session_id: str) -> dict[str, Any] | None:
        if self._remote_available:
            try:
                value = await self._redis.get(f"training:{session_id}")
                if value:
                    return json.loads(value)
            except Exception:
                self._remote_available = False
        return self._memory.get(session_id)

    async def delete(self, session_id: str) -> None:
        self._memory.pop(session_id, None)
        if self._remote_available:
            await self._redis.delete(f"training:{session_id}")

    async def close(self) -> None:
        await self._redis.aclose()

    @property
    def mode(self) -> str:
        return "redis" if self._remote_available else "memory"


state_store = SessionStateStore()

