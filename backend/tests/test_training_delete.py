import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Evaluation, Message, TrainingPlan, TrainingSession
from app.infrastructure.state_store import state_store
from app.main import app


async def seed_related_data(user_id: str, target_id: str, other_id: str) -> tuple[str, str]:
    async with session_factory() as db:
        training = await db.get(TrainingSession, target_id)
        assert training is not None
        training.status = "FINISHED"
        training.current_round = 2
        db.add(Message(session_id=target_id, round_no=1, speaker="USER", content="一段待删除的回答"))
        db.add(Evaluation(
            session_id=target_id, user_id=user_id,
            logic_score=3, appropriateness_score=3, impact_score=3,
            relevance_score=3, concision_score=3, overall_score=60,
            summary="待删除的评分", suggestions=[], style_tags=[],
        ))
        baseline_plan = TrainingPlan(
            user_id=user_id, focus_dimension="逻辑性", title="由待删除评分生成的计划",
            tasks=[{"key": "rewrite", "actionType": "REWRITE", "sourceSessionId": target_id}],
        )
        evidence_plan = TrainingPlan(
            user_id=user_id, focus_dimension="得体性", title="引用这次训练的其他计划",
            status="COMPLETED",
            tasks=[
                {"key": "course", "actionType": "COURSE", "completed": True, "evidence": None},
                {"key": "practice", "actionType": "TRAINING", "completed": True, "completedAt": "2026-10-22T08:00:00+00:00", "evidence": target_id},
                {"key": "rewrite", "actionType": "REWRITE", "sourceSessionId": other_id, "completed": True, "evidence": "改写内容", "rewritePassed": True},
                {"key": "retest", "actionType": "RETEST", "completed": True, "evidence": other_id},
            ],
        )
        db.add_all([baseline_plan, evidence_plan])
        await db.flush()
        ids = baseline_plan.id, evidence_plan.id
        await db.commit()
        return ids


async def related_state(target_id: str, baseline_plan_id: str, evidence_plan_id: str) -> tuple:
    async with session_factory() as db:
        messages = (await db.scalars(select(Message).where(Message.session_id == target_id))).all()
        evaluation = (await db.scalars(select(Evaluation).where(Evaluation.session_id == target_id))).all()
        baseline_plan = await db.get(TrainingPlan, baseline_plan_id)
        evidence_plan = await db.get(TrainingPlan, evidence_plan_id)
        return messages, evaluation, baseline_plan, evidence_plan


def test_delete_training_session_removes_related_data_and_protects_other_users() -> None:
    with TestClient(app, client=("198.51.100.80", 50125)) as client:
        def register(label: str) -> tuple[str, dict[str, str]]:
            response = client.post("/api/v1/auth/register", json={
                "email": f"delete-{label}-{uuid4().hex[:8]}@example.com",
                "password": "GraduateDesign123!", "displayName": label,
            })
            assert response.status_code == 201
            return response.json()["data"]["user"]["id"], {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}

        owner_id, owner_headers = register("记录主人")
        _, other_headers = register("其他学员")
        scene_id = client.get("/api/v1/scenes", headers=owner_headers).json()["data"][0]["id"]
        target_id = client.post("/api/v1/training-sessions", headers=owner_headers, json={"sceneId": scene_id}).json()["data"]["id"]
        other_id = client.post("/api/v1/training-sessions", headers=owner_headers, json={"sceneId": scene_id}).json()["data"]["id"]
        baseline_plan_id, evidence_plan_id = asyncio.run(seed_related_data(owner_id, target_id, other_id))

        assert client.delete(f"/api/v1/training-sessions/{target_id}").status_code == 401
        assert client.delete(f"/api/v1/training-sessions/{target_id}", headers=other_headers).status_code == 404
        assert client.post(f"/api/v1/training-sessions/{target_id}/archive", headers=owner_headers).status_code == 200

        removed = client.delete(f"/api/v1/training-sessions/{target_id}", headers=owner_headers)
        assert removed.status_code == 204
        assert client.get(f"/api/v1/training-sessions/{target_id}", headers=owner_headers).status_code == 404
        assert client.get(f"/api/v1/evaluations/{target_id}", headers=owner_headers).status_code == 404
        assert client.delete(f"/api/v1/training-sessions/{target_id}", headers=owner_headers).status_code == 404
        assert client.get(f"/api/v1/training-sessions/{other_id}", headers=owner_headers).status_code == 200
        assert all(item["id"] != target_id for item in client.get("/api/v1/training-sessions?archived=true", headers=owner_headers).json()["data"])

        messages, evaluations, baseline_plan, evidence_plan = asyncio.run(
            related_state(target_id, baseline_plan_id, evidence_plan_id)
        )
        assert not messages and not evaluations and baseline_plan is None
        assert evidence_plan is not None and evidence_plan.status == "ACTIVE"
        assert evidence_plan.tasks[0]["completed"] is True
        assert all(not task["completed"] and task["evidence"] is None for task in evidence_plan.tasks[1:])
        assert evidence_plan.tasks[2]["rewritePassed"] is False
        assert asyncio.run(state_store.get(target_id)) is None
