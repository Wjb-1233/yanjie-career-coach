"""编程笔试题与判题服务。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.errors import AppError
from app.db.models import CodingSubmission


def _find_problem_file() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "content" / "coding-problems.json"
        if candidate.is_file():
            return candidate
    return None


PROBLEM_FILE = _find_problem_file()
PROBLEMS: list[dict] = json.loads(PROBLEM_FILE.read_text(encoding="utf-8")) if PROBLEM_FILE else []


def list_problems() -> list[dict]:
    return [
        {
            "id": item["id"],
            "title": item["title"],
            "difficulty": item.get("difficulty", "入门"),
            "tags": item.get("tags", []),
            "description": item["description"],
            "languages": list((item.get("entry") or {}).keys()),
            "template": item.get("template", {}),
            "sample": (item.get("cases") or [{}])[0],
        }
        for item in PROBLEMS
    ]


def get_problem(problem_id: str) -> dict:
    for item in PROBLEMS:
        if item["id"] == problem_id:
            return item
    raise AppError(404, "CODING_PROBLEM_NOT_FOUND", "题目不存在")


async def judge(session, user_id: str, problem_id: str, language: str, code: str) -> dict:
    from app.features.coding.runner import run_cases

    problem = get_problem(problem_id)
    entry = (problem.get("entry") or {}).get(language)
    if not entry:
        raise AppError(422, "CODING_LANGUAGE_UNSUPPORTED", "这道题不支持该语言")
    if len(code.strip()) < 10:
        raise AppError(422, "CODING_CODE_EMPTY", "请先写一点代码再运行")

    started = time.perf_counter()
    try:
        results = run_cases(language, code, entry, problem.get("cases") or [])
        error = None
    except RuntimeError as exc:
        results = []
        error = str(exc)
    duration_ms = int((time.perf_counter() - started) * 1000)
    passed = sum(1 for item in results if item["passed"])
    total = len(problem.get("cases") or [])

    row = CodingSubmission(
        user_id=user_id,
        problem_id=problem_id,
        language=language,
        passed=passed,
        total=total,
        duration_ms=duration_ms,
        results=results,
    )
    session.add(row)
    await session.commit()
    return {
        "id": row.id,
        "problemId": problem_id,
        "language": language,
        "passed": passed,
        "total": total,
        "allPassed": total > 0 and passed == total,
        "durationMs": duration_ms,
        "results": results,
        "error": error,
        "createdAt": row.created_at.isoformat(),
    }
