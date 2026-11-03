"""故事库接口与提取逻辑测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.features.stories.service import fallback_stories, normalize_story
from app.main import app


def _auth(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"story-{uuid4().hex[:8]}@example.com", "password": "StoryTest123", "displayName": "故事"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def test_extract_falls_back_when_model_returns_empty(monkeypatch) -> None:
    """模型没提炼出内容时应退回规则提取，而不是直接报错。"""
    from app.features.stories import service

    async def empty_llm(*_args, **_kwargs):
        return {"stories": []}

    class Msg:
        def __init__(self, content: str) -> None:
            self.content = content

    monkeypatch.setattr(service.llm_gateway, "complete_json", empty_llm)
    assert service.fallback_stories([Msg("我负责订单系统，把 P99 从 800ms 降到 200ms，用 Redis 预扣库存。")])


def test_normalize_story_requires_title_and_action() -> None:
    assert normalize_story({"title": "", "action": "做了很多事"}) is None
    assert normalize_story({"title": "订单优化", "action": ""}) is None
    story = normalize_story({"title": "订单优化", "action": "用 Redis 预扣库存", "result": ""})
    assert story["result"] == "（未说明结果）"


def test_fallback_stories_prefers_quantified_answer() -> None:
    class Msg:
        def __init__(self, content: str) -> None:
            self.content = content

    messages = [Msg("简单说了一句"), Msg("我负责订单系统，把 P99 从 800ms 降到 200ms，用 Redis 预扣库存。")]
    stories = fallback_stories(messages)
    assert stories and "P99" in stories[0]["action"]


def test_story_crud_flow() -> None:
    with TestClient(app) as client:
        headers = _auth(client)
        created = client.post(
            "/api/v1/stories",
            headers=headers,
            json={"title": "订单系统优化", "situation": "下单链路慢", "task": "降延迟",
                  "action": "用 Redis 预扣库存，压测后上线", "result": "P99 从 800ms 降到 200ms", "tags": ["性能"]},
        )
        assert created.status_code == 201, created.text
        story = created.json()["data"]
        assert story["usageCount"] == 0

        used = client.post(f"/api/v1/stories/{story['id']}/use", headers=headers)
        assert used.json()["data"]["usageCount"] == 1

        updated = client.patch(f"/api/v1/stories/{story['id']}", headers=headers, json={"result": "P99 降到 180ms"})
        assert updated.json()["data"]["result"] == "P99 降到 180ms"

        listed = client.get("/api/v1/stories", headers=headers).json()["data"]
        assert len(listed) == 1

        deleted = client.delete(f"/api/v1/stories/{story['id']}", headers=headers)
        assert deleted.status_code == 204
        assert client.get("/api/v1/stories", headers=headers).json()["data"] == []
