from typing import Annotated

from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.auth import service
from app.features.auth.service import account_stats, change_password, set_avatar
from app.features.auth.schemas import (
    AccountDeleteRequest,
    AvatarRequest,
    DemoLoginRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordRequestInput,
    ProfileUpdateRequest,
    RegisterRequest,
    UserView,
)
from app.infrastructure.rate_limit import limit_login, limit_register

router = APIRouter(prefix="/auth", tags=["认证"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


def demo_request_allowed(request: Request) -> bool:
    if settings.environment != "development":
        return False
    source = request.headers.get("origin") or request.headers.get("referer") or ""
    parsed = urlsplit(source)
    try:
        return parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port in {4173, 5173}
    except ValueError:
        return False


def set_refresh_cookie(response: Response, token: str, max_age: int | None = None) -> None:
    response.set_cookie(
        "refresh_token",
        token,
        httponly=True,
        secure=settings.environment == "production",
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path=f"{settings.api_prefix}/auth",
        max_age=max_age or settings.refresh_token_days * 86400,
    )


@router.post("/register", status_code=201, dependencies=[Depends(limit_register)])
async def register(body: RegisterRequest, response: Response, session: DbSession) -> dict:
    result, refresh = await service.register(
        session, body.email, body.password, body.display_name
    )
    set_refresh_cookie(response, refresh)
    return ok(result.model_dump(by_alias=True))


@router.post("/login", dependencies=[Depends(limit_login)])
async def login(body: LoginRequest, response: Response, session: DbSession) -> dict:
    result, refresh = await service.login(session, body.email, body.password)
    set_refresh_cookie(response, refresh)
    return ok(result.model_dump(by_alias=True))


@router.get("/demo-status")
async def demo_status(request: Request) -> dict:
    return ok({"enabled": demo_request_allowed(request)})


@router.post("/demo-login", dependencies=[Depends(limit_login)])
async def demo_login(
    body: DemoLoginRequest, request: Request, response: Response, session: DbSession
) -> dict:
    if not demo_request_allowed(request):
        raise AppError(404, "DEMO_LOGIN_DISABLED", "演示登录未启用")
    result, refresh = await service.demo_login(session, body.role)
    set_refresh_cookie(response, refresh)
    return ok(result.model_dump(by_alias=True))


@router.post("/refresh")
async def refresh(
    response: Response,
    session: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    if not refresh_token:
        raise AppError(401, "REFRESH_MISSING", "缺少刷新令牌")
    result, new_refresh = await service.rotate_refresh(session, refresh_token)
    set_refresh_cookie(response, new_refresh)
    return ok(result.model_dump(by_alias=True))


@router.post("/logout")
async def logout(
    response: Response,
    session: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    await service.revoke_refresh(session, refresh_token)
    response.delete_cookie(
        "refresh_token",
        path=f"{settings.api_prefix}/auth",
        domain=settings.cookie_domain,
        secure=settings.environment == "production",
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    return ok(None)


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return ok(UserView.from_orm_user(user).model_dump(by_alias=True))


@router.post("/password-request")
async def password_request(body: PasswordRequestInput, session: DbSession) -> dict:
    await service.create_password_request(session, body.email)
    return ok({"submitted": True})


@router.delete("/me/delete")
async def delete_me(body: AccountDeleteRequest, user: CurrentUser, session: DbSession) -> dict:
    """注销账号：校验密码与确认词后删除个人数据与录像，不可恢复。"""
    from app.features.account.deletion import delete_account

    if body.confirm.strip() != "注销":
        raise AppError(400, "CONFIRM_REQUIRED", "请输入「注销」两个字确认")
    await delete_account(session, user, body.password)
    return ok({"deleted": True})


@router.patch("/me/password")
async def change_password_route(body: PasswordChangeRequest, user: CurrentUser, session: DbSession) -> dict:
    await change_password(session, user, body.current_password, body.new_password)
    return ok({"changed": True})


@router.put("/me/avatar")
async def update_avatar(body: AvatarRequest, user: CurrentUser, session: DbSession) -> dict:
    avatar = await set_avatar(session, user, body.data_url)
    return ok({"avatar": avatar})


@router.get("/me/export")
async def export_me(user: CurrentUser, session: DbSession) -> dict:
    """个人数据导出：账号、训练记录、评分、计划、话术、故事。"""
    from app.features.account.export import export_user_data

    return ok(await export_user_data(session, user))


@router.get("/me/stats")
async def my_stats(user: CurrentUser, session: DbSession) -> dict:
    return ok(await account_stats(session, user.id))


@router.patch("/me")
async def update_me(body: ProfileUpdateRequest, user: CurrentUser, session: DbSession) -> dict:
    user.display_name = body.display_name
    user.bio = body.bio
    await session.commit()
    return ok(UserView.from_orm_user(user).model_dump(by_alias=True))

