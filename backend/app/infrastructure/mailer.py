"""邮件发送：忘记密码链接。

未配置 SMTP 时不报错，只记日志；调用方会回退到管理员工单，
这样本地开发和没有邮件服务的部署都能用。
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def _send_sync(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password is not None:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


async def send_password_reset(to: str, link: str, minutes: int) -> bool:
    if not smtp_configured():
        logger.info("mail.skipped reason=smtp_not_configured to=%s", to)
        return False
    subject = "言阶 · 重置密码"
    body = (
        "你好，\n\n"
        f"我们收到了重置言阶账号密码的请求。请在 {minutes} 分钟内打开下面的链接设置新密码：\n\n"
        f"{link}\n\n"
        "如果这不是你本人操作，忽略这封邮件即可，原密码不会改变。\n\n"
        "— 言阶"
    )
    try:
        await asyncio.to_thread(_send_sync, to, subject, body)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("mail.send_failed error_type=%s", type(exc).__name__)
        return False
