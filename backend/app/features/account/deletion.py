"""注销账号：删除个人数据与媒体文件，操作不可恢复。"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import verify_password
from app.db.models import (
    AnalysisTask,
    CodingSubmission,
    CourseProgress,
    Evaluation,
    EvaluationEvidence,
    Favorite,
    GroupInterview,
    Message,
    MistakeState,
    ModelUsageDaily,
    PasswordResetRequest,
    PasswordResetToken,
    QuestionBankState,
    RefreshToken,
    ResumeContext,
    ResumeDiagnosis,
    Script,
    ShareRevocation,
    SkillState,
    Story,
    TrainingPlan,
    TrainingSession,
    User,
)
from app.features.recordings import storage

logger = logging.getLogger(__name__)

# 演示账号不允许注销，避免演示环境被清空
DEMO_EMAILS = {"student@example.com", "admin@example.com"}

# 只按 user_id 归属的独立子表：逐个批删，不依赖数据库的 ON DELETE CASCADE
OWNED_TABLES = (
    RefreshToken,
    Favorite,
    Script,
    PasswordResetRequest,
    PasswordResetToken,
    Story,
    SkillState,
    MistakeState,
    AnalysisTask,
    CourseProgress,
    TrainingPlan,
    ModelUsageDaily,
    QuestionBankState,
    ResumeDiagnosis,
    GroupInterview,
    CodingSubmission,
)


async def purge_user_rows(session: AsyncSession, user: User, session_ids: list[str]) -> None:
    """显式逐表清理该用户的全部行（含 27 个 user_id 外键之外的孤儿表）。

    SQLite 历史上不开启 PRAGMA foreign_keys，级联删除不会生效；这里按依赖顺序
    先删引用 evaluations 的行，再删会话与用户的直属行，最后才允许删除 users。
    """
    evaluation_ids = select(Evaluation.id).where(Evaluation.user_id == user.id)
    if session_ids:
        evaluation_ids = select(Evaluation.id).where(
            or_(Evaluation.user_id == user.id, Evaluation.session_id.in_(session_ids))
        )

    await session.execute(
        delete(EvaluationEvidence).where(EvaluationEvidence.evaluation_id.in_(evaluation_ids))
    )
    await session.execute(delete(Evaluation).where(Evaluation.id.in_(evaluation_ids)))

    if session_ids:
        await session.execute(delete(Message).where(Message.session_id.in_(session_ids)))
        await session.execute(
            delete(ResumeContext).where(ResumeContext.session_id.in_(session_ids))
        )
        # 撤销记录没有外键，会话删了也要一起清掉，否则令牌会一直指向空会话
        await session.execute(
            delete(ShareRevocation).where(ShareRevocation.session_id.in_(session_ids))
        )

    await session.execute(delete(TrainingSession).where(TrainingSession.user_id == user.id))
    for model in OWNED_TABLES:
        await session.execute(delete(model).where(model.user_id == user.id))


async def delete_account(session: AsyncSession, user: User, password: str) -> None:
    if user.email in DEMO_EMAILS:
        raise AppError(403, "DEMO_ACCOUNT_PROTECTED", "演示账号不能注销")
    if not verify_password(password, user.password_hash):
        raise AppError(403, "PASSWORD_INVALID", "密码不正确，未注销")

    sessions = (
        await session.scalars(
            select(TrainingSession).where(TrainingSession.user_id == user.id)
        )
    ).all()

    # 先删文件再删库：库删了之后就找不到这些文件了
    for item in sessions:
        storage.remove(item.recording_path)
        for segment in (item.delivery or {}).get("segments") or []:
            name = segment.get("file")
            if name:
                storage.remove(name)

    await purge_user_rows(session, user, [item.id for item in sessions])
    await session.delete(user)
    await session.commit()
    logger.info("account.deleted sessions=%s", len(sessions))
