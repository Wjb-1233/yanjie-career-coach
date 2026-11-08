"""简历诊断：关键词覆盖、打分与历史。"""

import io
import uuid

from fastapi.testclient import TestClient

from app.features.resume_diagnosis.service import analyze


def test_analyze_reports_matched_and_missing() -> None:
    resume = (
        "项目经历：订单协同系统，使用 Java 与 Spring Boot 开发，负责订单模块，"
        "把接口延迟从 800ms 降到 200ms，覆盖 3 个工厂。" * 3
    )
    jd = "岗位职责：负责订单系统后端开发。任职要求：熟悉 Java、Spring Boot、MySQL、Redis、消息队列。"
    result = analyze(resume, jd)
    assert "Java" in result["matched"]
    assert any("MySQL" in item for item in result["missing"])
    assert result["score"] > 0
    assert result["suggestions"]
    assert result["coverage"] > 0


def test_analyze_flags_missing_numbers() -> None:
    result = analyze("我做过一些项目，负责后端开发。", "需要熟悉 Java、Spring Boot、MySQL。")
    assert result["signals"]["digits"] == 0
    assert any("数字" in item["title"] for item in result["suggestions"])


def _headers(client: TestClient) -> dict:
    email = f"resume-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "ResumeTest123!", "displayName": "简历诊断"},
    )
    return {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}


def test_diagnose_with_pasted_text_and_history() -> None:
    from app.main import app

    resume = (
        "项目经历：制造业订单协同 Agent 系统，使用 LangGraph 与 Milvus，"
        "把订单处理时间从 2 小时降到 20 分钟，覆盖 3 个工厂。" * 3
    )
    jd = "岗位职责：负责后端服务开发。任职要求：熟悉 Java、MySQL、Redis、消息队列，有 Agent 项目经验优先。"
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v1/resume-diagnosis",
            data={"jdText": jd, "resumeText": resume},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["score"] >= 0
        assert data["summary"]

        history = client.get("/api/v1/resume-diagnosis", headers=headers).json()["data"]
        assert len(history) == 1
        detail = client.get(f"/api/v1/resume-diagnosis/{history[0]['id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["data"]["id"] == data["id"]


def _docx_bytes(text: str) -> bytes:
    import zipfile

    body = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.split("\n"))
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def test_diagnose_with_docx_upload() -> None:
    from app.main import app

    text = ("王同学 - 后端开发\n" + "项目经历：订单系统优化，使用 Java、Spring Boot、MySQL，接口延迟从 800ms 降到 200ms。\n") * 4
    content = _docx_bytes(text)

    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v1/resume-diagnosis",
            data={"jdText": "岗位职责：负责订单系统开发。任职要求：熟悉 Java、Spring Boot、MySQL、Redis。"},
            files={"file": ("resume.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["score"] > 0
