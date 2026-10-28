from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_script_versions_preserve_highlights_favorites_and_ownership() -> None:
    with TestClient(app, client=("198.51.100.79", 50125)) as client:
        tokens = []
        for suffix in ("owner", "stranger"):
            result = client.post("/api/v1/auth/register", json={
                "email": f"script-{suffix}-{uuid4().hex[:8]}@example.com",
                "password": "GraduateDesign123!", "displayName": suffix,
            })
            tokens.append(result.json()["data"]["accessToken"])
        owner = {"Authorization": f"Bearer {tokens[0]}"}
        stranger = {"Authorization": f"Bearer {tokens[1]}"}
        scene_id = client.get("/api/v1/scenes", headers=owner).json()["data"][0]["id"]

        generated = client.post("/api/v1/scripts/generate", headers=owner, json={
            "sceneId": scene_id, "objective": "回答为什么应聘这个岗位",
            "extraContext": "应届毕业生，提供真实课程项目经历",
        })
        assert generated.status_code == 201
        versions = generated.json()["data"]["versions"]
        assert len(versions) == 3
        script_id = versions[0]["id"]
        assert versions[0]["highlights"]
        assert client.post(f"/api/v1/scripts/{script_id}/favorite", headers=owner).json()["data"]["favorite"] is True
        assert [item["id"] for item in client.get("/api/v1/scripts/favorites", headers=owner).json()["data"]] == [script_id]
        assert client.get("/api/v1/scripts/favorites", headers=stranger).json()["data"] == []
        stored = client.get("/api/v1/scripts", headers=owner).json()["data"]
        assert next(item for item in stored if item["id"] == script_id)["highlights"] == versions[0]["highlights"]
        assert client.delete(f"/api/v1/scripts/{script_id}", headers=stranger).status_code == 404
        assert client.delete(f"/api/v1/scripts/{script_id}", headers=owner).status_code == 204
