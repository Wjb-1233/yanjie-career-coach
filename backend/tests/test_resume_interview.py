import asyncio
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.db.base import session_factory
from app.db.models import ResumeContext
from app.features.training.graph import prompt_node
from app.infrastructure.llm import llm_gateway
from app.main import app


def make_docx(text: str) -> bytes:
    data = BytesIO()
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    with ZipFile(data, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{escaped}</w:t></w:r></w:p></w:body></w:document>",
        )
    return data.getvalue()


async def resume_record(session_id: str) -> ResumeContext | None:
    async with session_factory() as db:
        return await db.get(ResumeContext, session_id)


def test_resume_interview_upload_question_followup_and_clear(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_question(system_prompt: str, user_prompt: str, **_kwargs):
        captured["opening_prompt"] = user_prompt
        return {"question": "你在 FastAPI 项目中为什么用 Redis 缓存，缓存失效时如何处理？"}

    async def fake_stream(system_prompt: str, _messages, **_kwargs):
        captured.setdefault("turn_prompts", []).append(system_prompt)
        yield "你在这个项目里如何设计缓存键与过期时间？"

    monkeypatch.setattr(llm_gateway, "complete_json", fake_question)
    monkeypatch.setattr(llm_gateway, "stream_text", fake_stream)
    with TestClient(app, client=("198.51.100.82", 50126)) as client:
        def register(name: str) -> dict[str, str]:
            response = client.post("/api/v1/auth/register", json={
                "email": f"resume-{uuid4().hex[:8]}@example.com",
                "password": "GraduateDesign123!", "displayName": name,
            })
            assert response.status_code == 201
            return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}

        owner = register("简历用户")
        other = register("其他用户")
        scene_id = client.get("/api/v1/scenes", headers=owner).json()["data"][0]["id"]
        resume_text = "我在毕业项目中负责 Python FastAPI 后端开发，并使用 Redis 做热点数据缓存，MySQL 保存业务数据。"
        file = ("我的简历.docx", make_docx(resume_text), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        assert client.post("/api/v1/training-sessions/with-resume", data={"sceneId": scene_id}, files={"file": file}).status_code == 401
        invalid = client.post("/api/v1/training-sessions/with-resume", headers=owner, data={"sceneId": scene_id}, files={"file": ("resume.doc", b"not a docx")})
        assert invalid.status_code == 422
        corrupted = client.post("/api/v1/training-sessions/with-resume", headers=owner, data={"sceneId": scene_id}, files={"file": ("resume.docx", b"not a zip")})
        assert corrupted.status_code == 422
        large = client.post("/api/v1/training-sessions/with-resume", headers=owner, data={"sceneId": scene_id}, files={"file": ("resume.docx", b"x" * (2 * 1024 * 1024 + 1))})
        assert large.status_code == 413

        created = client.post("/api/v1/training-sessions/with-resume", headers=owner, data={"sceneId": scene_id}, files={"file": file})
        assert created.status_code == 201, created.text
        item = created.json()["data"]
        session_id = item["id"]
        assert item["resumeFilename"] == "我的简历.docx"
        assert item["resumeOpeningDegraded"] is False
        assert "Redis 缓存" in item["messages"][0]["content"]
        assert "Redis" in captured["opening_prompt"]
        assert asyncio.run(resume_record(session_id)) is not None

        reloaded = client.get(f"/api/v1/training-sessions/{session_id}", headers=owner).json()["data"]
        assert reloaded["resumeFilename"] == "我的简历.docx"
        assert "content" not in reloaded or resume_text not in str(reloaded)
        state = {
            "round_no": 1, "max_rounds": 12, "user_text": "使用了 Redis",
            "scene_title": "技术面试", "role_name": "面试官",
            "scene_background": "面试", "scene_goal": "表达清楚",
            "stage": "DISCOVERY", "flags": [], "should_finish": False,
            "prompt": "", "resume_text": resume_text,
        }
        assert "Redis" in prompt_node(state)["prompt"]
        first_reply = client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=owner, json={"content": "我主要负责 Redis 缓存设计。"},
        )
        assert first_reply.status_code == 200
        assert "<resume>" in captured["turn_prompts"][0]
        restarted = client.post(f"/api/v1/training-sessions/{session_id}/restart", headers=owner)
        assert restarted.status_code == 201
        restarted_id = restarted.json()["data"]["id"]
        assert restarted.json()["data"]["resumeFilename"] == "我的简历.docx"
        assert asyncio.run(resume_record(restarted_id)) is not None
        assert client.delete(f"/api/v1/training-sessions/{restarted_id}", headers=owner).status_code == 204
        assert asyncio.run(resume_record(restarted_id)) is None
        assert client.delete(f"/api/v1/training-sessions/{session_id}/resume", headers=other).status_code == 404
        assert client.delete(f"/api/v1/training-sessions/{session_id}/resume", headers=owner).status_code == 204
        assert asyncio.run(resume_record(session_id)) is None
        assert client.get(f"/api/v1/training-sessions/{session_id}", headers=owner).json()["data"]["resumeFilename"] is None
        second_reply = client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=owner, json={"content": "缓存数据过期后会回源数据库。"},
        )
        assert second_reply.status_code == 200
        assert "<resume>" not in captured["turn_prompts"][1]

        generic = client.post("/api/v1/training-sessions", headers=owner, json={"sceneId": scene_id})
        assert generic.status_code == 201
        assert generic.json()["data"]["resumeFilename"] is None
