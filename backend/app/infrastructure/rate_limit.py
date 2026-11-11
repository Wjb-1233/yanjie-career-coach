import asyncio
import ipaddress
import time
from dataclasses import dataclass

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import settings
from app.core.errors import AppError


@dataclass(slots=True)
class MemoryCounter:
    count: int
    expires_at: float


class RateLimiter:
    def __init__(self) -> None:
        redis_password = (
            settings.redis_password.get_secret_value() if settings.redis_password else None
        )
        self._redis = Redis.from_url(
            settings.redis_url,
            password=redis_password,
            decode_responses=True,
        )
        self._remote_available = False
        self._memory: dict[str, MemoryCounter] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        if not settings.redis_enabled:
            return
        try:
            await self._redis.ping()
            self._remote_available = True
        except Exception:
            self._remote_available = False

    async def check(self, key: str, limit: int, window_seconds: int) -> None:
        count, retry_after = await self._increment(key, window_seconds)
        if count > limit:
            raise AppError(
                429,
                "RATE_LIMITED",
                "请求过于频繁，请稍后再试",
                headers={"Retry-After": str(max(1, retry_after))},
            )

    async def _increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        namespaced = f"rate:{key}"
        if self._remote_available:
            try:
                result = await self._redis.eval(
                    """
                    local count = redis.call('INCR', KEYS[1])
                    if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
                    return {count, redis.call('TTL', KEYS[1])}
                    """,
                    1,
                    namespaced,
                    window_seconds,
                )
                return int(result[0]), int(result[1])
            except Exception:
                self._remote_available = False

        now = time.monotonic()
        async with self._lock:
            current = self._memory.get(namespaced)
            if current is None or current.expires_at <= now:
                current = MemoryCounter(count=0, expires_at=now + window_seconds)
                self._memory[namespaced] = current
            current.count += 1
            retry_after = int(max(1, current.expires_at - now))
            if len(self._memory) > 10_000:
                self._memory = {
                    name: item for name, item in self._memory.items() if item.expires_at > now
                }
            return current.count, retry_after

    async def close(self) -> None:
        await self._redis.aclose()

    @property
    def mode(self) -> str:
        return "redis" if self._remote_available else "memory"


def resolve_client_ip(
    xff_value: str | None,
    peer_host: str | None,
    trusted_proxy_count: int,
) -> str:
    """XFF 形如「客户端, 代理1, 代理2」，只有确认了可信跳数才能从右侧数着取。

    trusted_proxy_count 为 0（默认）时不信任任何代理头，直接回落到 TCP 对端地址；
    否则取右侧第 trusted_proxy_count 跳——左侧条目完全由客户端控制，取它等于让攻击者自选限流键。
    跳数不够、条目为空或不是合法 IP 时同样回落到对端地址。
    """
    peer = (peer_host or "").strip() or "unknown"
    if trusted_proxy_count <= 0:
        return peer
    hops = [item.strip() for item in (xff_value or "").split(",")]
    if len(hops) < trusted_proxy_count:
        return peer
    candidate = hops[-trusted_proxy_count]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer
    return candidate


def client_identifier(request: Request) -> str:
    return resolve_client_ip(
        request.headers.get("X-Forwarded-For"),
        request.client.host if request.client else None,
        settings.trusted_proxy_count,
    )


rate_limiter = RateLimiter()


async def limit_login(request: Request) -> None:
    await rate_limiter.check(f"login:{client_identifier(request)}", 10, 60)


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def is_local_client(request: Request) -> bool:
    identified = client_identifier(request)
    return identified in LOCAL_HOSTS


async def limit_register(request: Request) -> None:
    # 本地开发与自测不限制注册频率，避免同一个人反复试注册被锁一小时
    if settings.environment != "production" and is_local_client(request):
        return
    await rate_limiter.check(f"register:{client_identifier(request)}", 5, 3600)


async def limit_model_user(user_id: str) -> None:
    """模型调用限流 + 每日配额 + 用量计数，一道口子管住成本。"""
    from app.core import metrics
    from app.core.errors import AppError

    await rate_limiter.check(f"model:{user_id}", 30, 60)

    if await _daily_calls(user_id) >= settings.model_daily_quota:
        metrics.incr_event("model_quota", "rejected")
        raise AppError(
            429,
            "MODEL_QUOTA_EXCEEDED",
            f"今天的模型调用额度（{settings.model_daily_quota} 次）已用完，明天再来或联系管理员",
        )

    await _record_usage(user_id)
    metrics.incr_event("model_quota", "allowed")


def _today() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).date().isoformat()


async def _daily_calls(user_id: str) -> int:
    from sqlalchemy import select

    from app.db.base import session_factory
    from app.db.models import ModelUsageDaily

    async with session_factory() as session:
        row = await session.get(ModelUsageDaily, {"user_id": user_id, "day": _today()})
        return int(row.calls) if row else 0


async def _record_usage(user_id: str) -> None:
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    from app.db.base import session_factory
    from app.db.models import ModelUsageDaily, now

    day = _today()
    async with session_factory() as session:
        row = await session.get(ModelUsageDaily, {"user_id": user_id, "day": day})
        if row is None:
            session.add(ModelUsageDaily(user_id=user_id, day=day, calls=1))
        else:
            row.calls = int(row.calls) + 1
        try:
            await session.commit()
        except IntegrityError:
            # 同一用户并发请求会同时插入，退化为原子 UPDATE
            await session.rollback()
            await session.execute(
                update(ModelUsageDaily)
                .where(ModelUsageDaily.user_id == user_id, ModelUsageDaily.day == day)
                .values(calls=ModelUsageDaily.calls + 1, updated_at=now())
            )
            await session.commit()


async def limit_client_error(request: Request) -> None:
    # 前端错误上报：单 IP 每分钟 20 条，防止被当成写入接口刷
    await rate_limiter.check(f"client-error:{client_identifier(request)}", 20, 60)
