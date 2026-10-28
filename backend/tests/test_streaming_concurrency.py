import asyncio
from uuid import uuid4

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_streaming_auth_does_not_exhaust_database_pool() -> None:
    """16 streams exceeded SQLite's 15-connection pool before function-scope auth."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"stream-{uuid4().hex[:8]}@example.com",
                    "password": "GraduateDesign123!",
                    "displayName": "并发测试学员",
                },
            )
            assert registered.status_code == 201
            token = registered.json()["data"]["accessToken"]
            headers = {"Authorization": f"Bearer {token}"}
            scenes = (await client.get("/api/v1/scenes", headers=headers)).json()["data"]

            async def complete_one_turn() -> httpx.Response:
                created = await client.post(
                    "/api/v1/training-sessions",
                    headers=headers,
                    json={"sceneId": scenes[0]["id"]},
                )
                assert created.status_code == 201
                session_id = created.json()["data"]["id"]
                return await client.post(
                    f"/api/v1/training-sessions/{session_id}/messages",
                    headers=headers,
                    json={"content": "我会先说明事实和影响，再提出明确的协作请求。"},
                    timeout=10,
                )

            responses = await asyncio.wait_for(
                asyncio.gather(*(complete_one_turn() for _ in range(16))),
                timeout=15,
            )

    assert all(response.status_code == 200 for response in responses)
    assert all("event: token" in response.text for response in responses)
    assert all("event: done" in response.text for response in responses)
