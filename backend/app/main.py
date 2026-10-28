from contextlib import asynccontextmanager
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

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
from app.infrastructure.state_store import state_store
from app.infrastructure.rate_limit import rate_limiter
from app.infrastructure.llm import llm_gateway

configure_logging(settings.log_level)
logger = logging.getLogger("app.http")


@asynccontextmanager
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
    yield
    await rate_limiter.close()
    await state_store.close()
    await engine.dispose()


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
):
    app.include_router(api_router, prefix=settings.api_prefix)

