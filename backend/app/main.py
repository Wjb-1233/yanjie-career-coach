from contextlib import asynccontextmanager
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.errors import (
    AppError,
    app_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging
from app.db.base import Base, engine, session_factory
from app.db.migrations import assert_database_is_current
from app.db.seed import seed_database
from app.features.admin.router import router as admin_router
from app.features.ability.router import router as ability_router
from app.features.auth.router import router as auth_router
from app.features.courses.router import router as courses_router
from app.features.dashboard.router import router as dashboard_router
from app.features.evaluations.router import router as evaluations_router
from app.features.health.router import router as health_router
from app.features.plans.router import router as plans_router
from app.features.scenes.router import router as scenes_router
from app.features.scripts.router import router as scripts_router
from app.features.training.router import router as training_router
from app.features.tasks.router import router as tasks_router
from app.features.video.router import router as video_router
from app.features.voice.router import router as voice_router
from app.infrastructure.state_store import state_store
from app.infrastructure.rate_limit import rate_limiter
from app.infrastructure.llm import llm_gateway

configure_logging(settings.log_level)
logger = logging.getLogger("app.http")


async def _recording_janitor() -> None:
    """每 6 小时清一次过期录制；测试环境不启动。"""
    import asyncio as _asyncio

    from app.db.base import session_factory
    from app.features.recordings.cleanup import purge_expired

    while True:
        try:
            async with session_factory() as db:
                await purge_expired(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("recordings.janitor_failed error_type=%s", type(exc).__name__)
        await _asyncio.sleep(6 * 3600)


async def warmup_models() -> None:
    """后台预热语音与人脸模型，避免第一个用户等 20 多秒。"""
    import asyncio as _asyncio

    from app.features.evaluations.delivery import warmup as voice_warmup
    from app.features.video.metrics import warmup as video_warmup

    try:
        await _asyncio.to_thread(voice_warmup)
        await _asyncio.to_thread(video_warmup)
        logger.info("models.warmed_up")
    except Exception as exc:  # noqa: BLE001
        logger.warning("models.warmup_failed error_type=%s", type(exc).__name__)


async def lifespan(_: FastAPI):
    if settings.environment == "production":
        await assert_database_is_current()
    elif settings.auto_create_schema:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    await state_store.initialize()
    await rate_limiter.initialize()
    if settings.environment == "production":
        await llm_gateway.health_status(force=True)
    async with session_factory() as session:
        await seed_database(session, include_demo_users=settings.environment != "production")
    # 自动清理只在生产环境跑，开发/测试/演示环境用后台按钮手动触发
    warmup_task = None
    if settings.environment != "test" and settings.model_warmup_enabled:
        import asyncio as _asyncio

        warmup_task = _asyncio.create_task(warmup_models())

    worker_enabled = settings.environment != "test"
    if worker_enabled:
        from app.features.tasks.service import start_worker

        start_worker()

    janitor_task = None
    if settings.environment == "production" and settings.recording_janitor_enabled:
        import asyncio as _asyncio

        janitor_task = _asyncio.create_task(_recording_janitor())
    yield
    if warmup_task is not None:
        warmup_task.cancel()
    if janitor_task is not None:
        janitor_task.cancel()
    if worker_enabled:
        from app.features.tasks.service import stop_worker

        await stop_worker()
    await rate_limiter.close()
    await state_store.close()
    await engine.dispose()


MEDIA_ROOT = settings.lesson_video_dir_path
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    expose_headers=["X-Request-Id"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-Id") or str(uuid4())
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    logger.info(
        "request.completed",
        extra={
            "request_id": request.state.request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
        },
    )
    return response


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)

for api_router in (
    health_router,
    auth_router,
    scenes_router,
    scripts_router,
    training_router,
    evaluations_router,
    ability_router,
    courses_router,
    plans_router,
    dashboard_router,
    admin_router,
    voice_router,
    video_router,
    tasks_router,
):
    app.include_router(api_router, prefix=settings.api_prefix)




@app.get("/api/v1/voice/status", tags=["语音对话"])
async def _voice_status_root() -> dict:
    from app.features.voice.router import realtime_configured

    return {"ok": True, "data": {"enabled": realtime_configured()}}


app.mount("/media/lessons", StaticFiles(directory=str(MEDIA_ROOT)), name="lessons")

RECORDING_ROOT = settings.recording_dir_path
RECORDING_ROOT.mkdir(parents=True, exist_ok=True)

from app.features.recordings.router import router as recordings_router  # noqa: E402

app.include_router(recordings_router)

