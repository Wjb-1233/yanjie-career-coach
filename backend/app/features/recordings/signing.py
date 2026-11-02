"""录制回放的签名链接。

浏览器播放 <video>/<audio> 时无法带 Authorization 头，所以回放地址用
短期签名（HMAC + 过期时间）代替裸 UUID：链接不可猜、会过期，
拿到链接也只能在有效期内访问。
"""

from __future__ import annotations

import hashlib
import hmac
import time

from app.core.config import settings

DEFAULT_TTL_SECONDS = 30 * 60


def _key() -> bytes:
    return (settings.recording_signing_secret or settings.jwt_secret).encode("utf-8")


def _digest(name: str, expires: int) -> str:
    message = f"{name}:{expires}".encode("utf-8")
    return hmac.new(_key(), message, hashlib.sha256).hexdigest()[:32]


def sign(name: str, ttl: int = DEFAULT_TTL_SECONDS) -> tuple[str, int]:
    expires = int(time.time()) + ttl
    return _digest(name, expires), expires


def verify(name: str, token: str, expires: int) -> bool:
    if not token or not name:
        return False
    if expires < int(time.time()):
        return False
    expected = _digest(name, expires)
    return hmac.compare_digest(expected, token)
