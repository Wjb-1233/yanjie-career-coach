"""编程笔试：题目、判题与提交历史。"""

import shutil
import uuid

from fastapi.testclient import TestClient

CORRECT_PY = """
def two_sum(nums, target):
    seen = {}
    for i, value in enumerate(nums):
        if target - value in seen:
            return [seen[target - value], i]
        seen[value] = i
"""

WRONG_PY = """
def two_sum(nums, target):
    return [0, 0]
"""

CORRECT_JS = """
function twoSum(nums, target) {
  const seen = new Map();
  for (let i = 0; i < nums.length; i += 1) {
    if (seen.has(target - nums[i])) return [seen.get(target - nums[i]), i];
    seen.set(nums[i], i);
  }
}
"""


def _headers(client: TestClient) -> dict:
    email = f"code-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CodeTest123!", "displayName": "编程"},
    )
    return {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}


def test_problems_listed() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _headers(client)
        problems = client.get("/api/v1/coding/problems", headers=headers).json()["data"]
        assert len(problems) >= 3
        assert problems[0]["languages"] == ["python", "javascript"]
        assert problems[0]["template"]["python"]


def test_python_solution_passes_and_history_saved() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _headers(client)
        result = client.post(
            "/api/v1/coding/problems/coding-two-sum/run",
            json={"language": "python", "code": CORRECT_PY},
            headers=headers,
        )
        assert result.status_code == 200, result.text
        data = result.json()["data"]
        assert data["allPassed"] is True
        assert data["passed"] == data["total"] == 3

        wrong = client.post(
            "/api/v1/coding/problems/coding-two-sum/run",
            json={"language": "python", "code": WRONG_PY},
            headers=headers,
        ).json()["data"]
        assert wrong["allPassed"] is False
        assert wrong["passed"] < wrong["total"]

        history = client.get("/api/v1/coding/submissions", headers=headers).json()["data"]
        assert len(history) == 2


def test_javascript_solution_passes() -> None:
    if not shutil.which("node"):
        import pytest

        pytest.skip("node 不可用")
    from app.main import app

    with TestClient(app) as client:
        headers = _headers(client)
        result = client.post(
            "/api/v1/coding/problems/coding-two-sum/run",
            json={"language": "javascript", "code": CORRECT_JS},
            headers=headers,
        )
        assert result.status_code == 200, result.text
        assert result.json()["data"]["allPassed"] is True
