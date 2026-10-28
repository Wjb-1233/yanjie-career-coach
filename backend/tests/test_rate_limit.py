import pytest

from app.core.errors import AppError
from app.infrastructure.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_memory_rate_limiter_rejects_after_limit() -> None:
    limiter = RateLimiter()
    await limiter.check("test-user", limit=2, window_seconds=60)
    await limiter.check("test-user", limit=2, window_seconds=60)

    with pytest.raises(AppError) as captured:
        await limiter.check("test-user", limit=2, window_seconds=60)

    assert captured.value.status_code == 429
    assert captured.value.headers is not None
    assert int(captured.value.headers["Retry-After"]) >= 1
    await limiter.close()
