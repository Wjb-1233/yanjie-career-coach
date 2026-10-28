from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.core.responses import ok
from app.db.base import session_factory
from app.infrastructure.knowledge import knowledge_store
from app.infrastructure.llm import llm_gateway
from app.infrastructure.state_store import state_store
from app.infrastructure.rate_limit import rate_limiter

router = APIRouter(tags=["系统状态"])


@router.get("/health")
async def health() -> dict:
    return ok({"status": "ok"})


@router.get("/ready")
async def ready(response: Response) -> dict:
    database = "ok"
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    llm = await llm_gateway.health_status()
    checks = {
        "database": database,
        "sessionState": state_store.mode if settings.redis_enabled else "disabled",
        "rateLimit": rate_limiter.mode if settings.redis_enabled else "disabled",
        "vectorStore": knowledge_store.mode if settings.milvus_enabled else "disabled",
        "llm": llm,
    }
    required_checks_ok = database == "ok"
    if settings.environment == "production":
        required_checks_ok = required_checks_ok and all(
            (
                checks["sessionState"] == "redis",
                checks["rateLimit"] == "redis",
                checks["vectorStore"] == "milvus",
                checks["llm"] == "ok",
            )
        )
    readiness = "ok" if required_checks_ok else "degraded"
    if readiness != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ok(
        {
            "status": readiness,
            "checks": checks,
        }
    )

