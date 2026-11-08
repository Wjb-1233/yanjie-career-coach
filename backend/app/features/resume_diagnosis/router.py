"""简历诊断接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import ResumeDiagnosis
from app.features.resume_diagnosis.service import analyze
from app.features.training.resume import MAX_RESUME_BYTES, parse_resume

router = APIRouter(prefix="/resume-diagnosis", tags=["简历诊断"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=201)
async def diagnose(
    user: CurrentUser,
    session: DbSession,
    jdText: Annotated[str, Form()],
    resumeText: Annotated[str, Form()] = "",
    file: Annotated[UploadFile | None, File()] = None,
) -> dict:
    jd = (jdText or "").strip()
    if len(jd) < 20:
        raise AppError(422, "JD_TOO_SHORT", "岗位 JD 至少填 20 个字")

    filename = ""
    resume = (resumeText or "").strip()
    if file is not None:
        content = await file.read(MAX_RESUME_BYTES + 1)
        await file.close()
        filename, resume = parse_resume(file.filename or "", content)
    if len(resume) < 100:
        raise AppError(422, "RESUME_TOO_SHORT", "简历内容至少 100 个字，或上传 .docx 简历")

    result = analyze(resume, jd)
    row = ResumeDiagnosis(
        user_id=user.id,
        filename=filename or "粘贴文本",
        score=result["score"],
        coverage=result["coverage"],
        result=result,
        jd_excerpt=jd[:200],
    )
    session.add(row)
    await session.commit()
    return ok({"id": row.id, **result, "filename": row.filename, "createdAt": row.created_at.isoformat()})


@router.get("")
async def history(user: CurrentUser, session: DbSession, limit: int = 10) -> dict:
    rows = (
        await session.scalars(
            select(ResumeDiagnosis)
            .where(ResumeDiagnosis.user_id == user.id)
            .order_by(ResumeDiagnosis.created_at.desc())
            .limit(max(1, min(limit, 30)))
        )
    ).all()
    return ok(
        [
            {
                "id": row.id,
                "score": row.score,
                "coverage": row.coverage,
                "filename": row.filename,
                "jdExcerpt": row.jd_excerpt,
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ]
    )


@router.get("/{diagnosis_id}")
async def detail(diagnosis_id: str, user: CurrentUser, session: DbSession) -> dict:
    row = await session.get(ResumeDiagnosis, diagnosis_id)
    if row is None or row.user_id != user.id:
        from app.core.errors import not_found

        raise not_found("简历诊断")
    return ok(
        {
            "id": row.id,
            "filename": row.filename,
            "createdAt": row.created_at.isoformat(),
            **(row.result or {}),
        }
    )
