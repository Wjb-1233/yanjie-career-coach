import pytest

from app.features.plans.generation import generate_plan
from app.infrastructure.llm import llm_gateway


@pytest.mark.asyncio
async def test_llm_generates_valid_personalized_lesson(monkeypatch) -> None:
    seen = {}

    async def fake_complete(system_prompt, user_prompt, **_kwargs):
        seen["prompt"] = user_prompt
        return {
            "title": "7 天针对性提升计划",
            "lesson": {
                "title": "先回应面试官的问题",
                "intro": "你上次没有直接回应追问，本课练习先回答、再举例、最后收束。",
                "steps": [
                    {"title": "先给答案", "explanation": "第一句直接回应对方最关心的问题。", "example": "我认为延期的主要原因是需求确认晚了两天。"},
                    {"title": "补充证据", "explanation": "用可验证的事实支撑自己的判断。", "example": "需求确认记录显示，关键决策在周三才完成。"},
                    {"title": "明确行动", "explanation": "最后明确负责人和下一步的时间。", "example": "我今天会补齐计划，明天下午给出新节点。"},
                ],
                "exercise": "请重写你对面试官追问的回答，并包含结论、证据和下一步。",
            },
            "practice_task": "回到原场景完成六轮追问训练",
            "rewrite_task": "改写两句没有直接回答追问的话",
            "retest_task": "复测并对比针对性与五维评分",
        }

    monkeypatch.setattr(type(llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)
    draft = await generate_plan(
        focus="针对性",
        scores={"logic": 4, "appropriateness": 4, "impact": 3, "relevance": 2, "concision": 4},
        suggestions=[{"problem": "没有直接回答", "rewrite": "先给结论"}],
        user_lines=["我觉得这个项目有点复杂，可能还需要继续看看。"],
        scene_title="压力面试",
        course_title="回应关切",
        course_content="先回应问题；给出依据；明确行动",
    )
    assert draft.lesson.ai_generated is True
    assert len(draft.lesson.steps) == 3
    assert "我觉得这个项目" in seen["prompt"]
