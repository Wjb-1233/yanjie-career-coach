"""注销账号与前端错误上报。"""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> tuple[dict[str, str], str]:
    email = f"{prefix}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "DeleteTest123!", "displayName": "注销", "consent": True},
    )
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}, email


def test_delete_account_requires_confirm_and_password() -> None:
    with TestClient(app, client=(f"delete-{uuid4().hex}", 50140)) as client:
        headers, email = _register(client, "delete")

        wrong_confirm = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "DeleteTest123!", "confirm": "删除"},
        )
        assert wrong_confirm.status_code == 400
        assert wrong_confirm.json()["title"] == "CONFIRM_REQUIRED"

        wrong_password = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "WrongPassword123!", "confirm": "注销"},
        )
        assert wrong_password.status_code == 403
        assert wrong_password.json()["title"] == "PASSWORD_INVALID"

        ok = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "DeleteTest123!", "confirm": "注销"},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["data"]["deleted"] is True

        # 账号已删除：登录失败、旧 token 失效
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "DeleteTest123!"},
            headers={"Referer": "http://testserver/"},
        )
        assert login.status_code == 401
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_delete_account_removes_private_data() -> None:
    with TestClient(app, client=(f"delete-{uuid4().hex}", 50141)) as client:
        headers, _ = _register(client, "delete")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene})

        response = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "DeleteTest123!", "confirm": "注销"},
        )
        assert response.status_code == 200

        fresh_headers, _ = _register(client, "another")
        export = client.get("/api/v1/auth/me/export", headers=fresh_headers).json()["data"]
        assert export["sessions"] == []


# 注销后必须归零的子表：既有 27 个 user_id 外键，也有只存 session_id 的孤儿表
USER_SCOPED_TABLES = (
    "refresh_tokens",
    "favorites",
    "scripts",
    "skill_states",
    "model_usage_daily",
    "stories",
    "mistake_states",
    "analysis_tasks",
    "training_plans",
    "course_progress",
    "password_reset_tokens",
    "password_reset_requests",
    "resume_diagnoses",
    "group_interviews",
    "coding_submissions",
    "ability_attempts",
    "evaluations",
    "training_sessions",
)
SESSION_SCOPED_TABLES = ("messages", "resume_contexts", "share_revocations")


def _row_counts(user_id: str, session_ids: list[str]) -> dict[str, int]:
    """直接用 SQL 计数，避开 ORM 的身份映射缓存。"""

    async def run() -> dict[str, int]:
        from sqlalchemy import bindparam, text

        from app.db.base import session_factory

        counts: dict[str, int] = {}
        async with session_factory() as db:
            for table in USER_SCOPED_TABLES:
                counts[table] = int(
                    (
                        await db.execute(
                            text(f"SELECT COUNT(*) FROM {table} WHERE user_id = :uid"),
                            {"uid": user_id},
                        )
                    ).scalar()
                    or 0
                )
            for table in SESSION_SCOPED_TABLES:
                counts[table] = int(
                    (
                        await db.execute(
                            text(f"SELECT COUNT(*) FROM {table} WHERE session_id IN :sids").bindparams(
                                bindparam("sids", expanding=True)
                            ),
                            {"sids": session_ids},
                        )
                    ).scalar()
                    or 0
                )
            counts["evaluation_evidence"] = int(
                (
                    await db.execute(
                        text(
                            "SELECT COUNT(*) FROM evaluation_evidence WHERE evaluation_id IN "
                            "(SELECT id FROM evaluations WHERE user_id = :uid)"
                        ),
                        {"uid": user_id},
                    )
                ).scalar()
                or 0
            )
        return counts

    return asyncio.run(run())


def _seed_child_rows(user_id: str, session_id: str, scene_id: str) -> None:
    """补齐只靠接口造不出来的行：技能状态、用量、收藏、话术。"""

    async def run() -> None:
        from datetime import UTC, datetime, timedelta

        from app.db.base import session_factory
        from app.db.models import (
            Favorite,
            ModelUsageDaily,
            RefreshToken,
            Script,
            SkillState,
            Story,
        )

        async with session_factory() as db:
            db.add_all(
                [
                    RefreshToken(
                        user_id=user_id,
                        token_hash=uuid4().hex + uuid4().hex,
                        expires_at=datetime.now(UTC) + timedelta(days=7),
                    ),
                    SkillState(user_id=user_id, dimension="seed-check"),
                    Favorite(user_id=user_id, scene_id=scene_id),
                    Script(user_id=user_id, scene_id=scene_id, style="STAR", content="先给结论，再补依据"),
                    Story(
                        user_id=user_id,
                        title="项目经历",
                        situation="s",
                        task="t",
                        action="a",
                        result="r",
                    ),
                    ModelUsageDaily(user_id=user_id, day="2025-01-02", calls=3),
                ]
            )
            await db.commit()

    asyncio.run(run())


def _admin_session_rows(client: TestClient, admin_headers: dict[str, str]) -> int:
    """翻完所有分页再数行：概览的会话数是原始表计数，列表是按用户内连接的结果。"""
    total = 0
    page = 0
    while True:
        rows = client.get(
            "/api/v1/admin/sessions", headers=admin_headers, params={"page": page, "size": 100}
        ).json()["data"]
        total += len(rows)
        if len(rows) < 100:
            return total
        page += 1


def test_sqlite_connections_enforce_foreign_keys() -> None:
    async def run() -> int:
        from app.db.base import engine

        async with engine.connect() as connection:
            return int((await connection.exec_driver_sql("PRAGMA foreign_keys")).scalar() or 0)

    assert asyncio.run(run()) == 1


def test_delete_account_purges_every_child_table() -> None:
    with TestClient(app, client=(f"delete-{uuid4().hex}", 50143)) as client:
        headers, _ = _register(client, "purge")
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]
        scene_id = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        session_id = client.post(
            "/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id}
        ).json()["data"]["id"]
        for index in range(2):
            client.post(
                f"/api/v1/training-sessions/{session_id}/messages/complete",
                headers=headers,
                json={"content": f"第{index + 1}轮：先说结论，再补依据。"},
            )
        assert (
            client.post(
                f"/api/v1/training-sessions/{session_id}/finish?create_plan=false", headers=headers
            ).status_code
            == 200
        )
        _seed_child_rows(user_id, session_id, scene_id)

        before = _row_counts(user_id, [session_id])
        for table in ("training_sessions", "messages", "evaluations", "scripts", "favorites",
                      "refresh_tokens", "skill_states", "model_usage_daily"):
            assert before[table] > 0, f"{table} 注销前就没有数据，用例失去意义"

        response = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "DeleteTest123!", "confirm": "注销"},
        )
        assert response.status_code == 200, response.text

        after = _row_counts(user_id, [session_id])
        assert {name: count for name, count in after.items() if count} == {}

        # 管理台的两个入口必须自洽：概览里的会话数等于会话列表的总条数
        admin = client.post(
            "/api/v1/auth/login", json={"email": "admin@example.com", "password": "Admin123!"}
        )
        assert admin.status_code == 200, admin.text
        admin_headers = {"Authorization": f"Bearer {admin.json()['data']['accessToken']}"}
        overview = client.get("/api/v1/admin/overview", headers=admin_headers).json()["data"]
        assert overview["sessions"] == _admin_session_rows(client, admin_headers)


def test_client_error_report_is_accepted_and_counted() -> None:
    from app.core import metrics

    before = metrics.render().count('app_events_total{event="client_error",outcome="received"}')
    with TestClient(app, client=(f"telemetry-{uuid4().hex}", 50142)) as client:
        response = client.post(
            "/api/v1/client-errors",
            json={"message": "TypeError: x is undefined", "route": "/report/1", "stack": "at foo()"},
        )
        assert response.status_code == 204

        oversized = client.post("/api/v1/client-errors", json={"message": "x" * 400})
        assert oversized.status_code == 422

    after = metrics.render()
    assert 'app_events_total{event="client_error",outcome="received"}' in after
    assert after.count('app_events_total{event="client_error",outcome="received"}') == before + 1