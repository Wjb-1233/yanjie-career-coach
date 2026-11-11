"""从 JD 起草场景：模型输出清洗、降级兜底、长度校验。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


LONG_JD = """岗位职责：
1. 负责后端服务的设计与开发，保证接口性能与稳定性；
2. 熟悉 MySQL、Redis，能够独立完成数据模型设计；
3. 参与线上故障排查与性能优化，推动问题闭环；
4. 具备良好的沟通能力，能与产品和前端协作推进项目。
任职要求：
5. 本科及以上学历，计算机相关专业；
6. 有高并发系统经验者优先。"""


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:8]}@example.com", "password": "DraftTest123!", "displayName": "起草", "consent": True},
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _force_model(monkeypatch, module, handler) -> None:
    monkeypatch.setattr(type(module.llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(module.llm_gateway, "complete_json", handler, raising=False)


def test_draft_uses_model_output(monkeypatch) -> None:
    from app.features.scenes import draft as module

    async def fake_complete(system, user, **kwargs):
        return {
            "title": "后端开发-技术一面",
            "industry": "互联网",
            "position": "后端开发工程师",
            "roleName": "技术面试官",
            "category": "技术一面",
            "difficulty": "中级",
            "background": "负责后端服务设计与性能优化。",
            "goal": "考察接口设计、数据模型与故障排查。",
            "openingLine": "你好，我是技术面试官，我们从项目开始聊。",
            "competency": "技术深度",
            "questions": [
                {"text": "你设计过的最复杂的接口是什么，怎么保证性能", "dimension": "内容与逻辑"},
                {"text": "MySQL 索引失效你遇到过哪些情况", "dimension": "信息完整"},
                {"text": "线上接口超时你怎么定位和止损", "dimension": "贴合问题"},
            ],
        }

    _force_model(monkeypatch, module, fake_complete)

    with TestClient(app, client=(f"draft-{uuid4().hex}", 50070)) as client:
        headers = _register(client, "draft")
        response = client.post(
            "/api/v1/my-scenes/draft-from-jd",
            headers=headers,
            json={"jd": LONG_JD, "position": "后端开发工程师", "category": "技术一面", "difficulty": "中级"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["degraded"] is False
        assert data["competency"] == "技术深度"
        assert len(data["questions"]) == 3
        assert all(item["dimension"] for item in data["questions"])


def test_draft_degrades_when_model_fails(monkeypatch) -> None:
    from app.features.scenes import draft as module

    async def boom(*args, **kwargs):
        raise RuntimeError("model down")

    _force_model(monkeypatch, module, boom)

    with TestClient(app, client=(f"draft-{uuid4().hex}", 50071)) as client:
        headers = _register(client, "draft")
        response = client.post(
            "/api/v1/my-scenes/draft-from-jd",
            headers=headers,
            json={"jd": LONG_JD, "position": "后端开发工程师"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["degraded"] is True
        assert 4 <= len(data["questions"]) <= 8


def test_draft_rejects_short_jd() -> None:
    with TestClient(app, client=(f"draft-{uuid4().hex}", 50072)) as client:
        headers = _register(client, "draft")
        response = client.post(
            "/api/v1/my-scenes/draft-from-jd",
            headers=headers,
            json={"jd": "招后端", "position": "后端"},
        )
        assert response.status_code == 422
        assert response.json()["title"] == "JD_TOO_SHORT"


def test_draft_result_can_be_saved(monkeypatch) -> None:
    from app.features.scenes import draft as module

    async def fake_complete(system, user, **kwargs):
        return {
            "title": "测试岗位-技术一面",
            "industry": "互联网",
            "position": "测试工程师",
            "roleName": "面试官",
            "category": "技术一面",
            "difficulty": "中级",
            "background": "负责质量保障。",
            "goal": "考察测试设计。",
            "openingLine": "你好，聊聊你的测试经验。",
            "competency": "技术深度",
            "questions": [
                {"text": "你怎么设计一个登录功能的测试用例", "dimension": "内容与逻辑"},
                {"text": "线上出现偶现 bug 你怎么排查", "dimension": "信息完整"},
            ],
        }

    _force_model(monkeypatch, module, fake_complete)

    with TestClient(app, client=(f"draft-{uuid4().hex}", 50073)) as client:
        headers = _register(client, "draft")
        data = client.post(
            "/api/v1/my-scenes/draft-from-jd",
            headers=headers,
            json={"jd": LONG_JD, "position": "测试工程师"},
        ).json()["data"]
        saved = client.post(
            "/api/v1/my-scenes",
            headers=headers,
            json={
                "title": data["title"],
                "industry": data["industry"],
                "position": data["position"],
                "roleName": data["roleName"],
                "category": data["category"],
                "difficulty": data["difficulty"],
                "background": data["background"],
                "goal": data["goal"],
                "openingLine": data["openingLine"],
                "competency": data["competency"],
                "questions": data["questions"],
            },
        )
        assert saved.status_code == 201, saved.text
