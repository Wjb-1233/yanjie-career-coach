from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.db.base import get_session
from app.db.models import User

password_hasher = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user: User) -> tuple[str, int]:
    expires_seconds = settings.access_token_minutes * 60
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)
    token = jwt.encode(
        {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": datetime.now(timezone.utc),
            "exp": expires_at,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_seconds


def decode_user_id(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials is None:
        raise AppError(401, "UNAUTHORIZED", "请先登录")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iss", "aud", "iat"]},
        )
        user_id = payload.get("sub")
    except InvalidTokenError as exc:
        raise AppError(401, "TOKEN_INVALID", "登录状态无效或已过期") from exc
    if not isinstance(user_id, str) or not user_id:
        raise AppError(401, "TOKEN_INVALID", "登录状态无效或已过期")
    return user_id


async def load_current_user(
    credentials: HTTPAuthorizationCredentials | None,
    session: AsyncSession,
) -> User:
    user_id = decode_user_id(credentials)
    user = await session.get(User, user_id)
    if user is None or not user.active:
        raise AppError(401, "USER_INVALID", "用户不存在或已停用")
    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    return await load_current_user(credentials, session)


async def get_streaming_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> User:
    """Authenticate before streaming and release the DB connection immediately.

    Streaming endpoints must not keep the authentication session checked out for
    the lifetime of the response. Their generators open their own short sessions.
    """
    return await load_current_user(credentials, session)


CurrentUser = Annotated[User, Depends(get_current_user)]
StreamingUser = Annotated[User, Depends(get_streaming_user, scope="function")]


def require_admin(user: CurrentUser) -> User:
    if user.role != "ADMIN":
        raise AppError(403, "FORBIDDEN", "当前账号没有管理员权限")
    return user


AdminUser = Annotated[User, Depends(require_admin)]

