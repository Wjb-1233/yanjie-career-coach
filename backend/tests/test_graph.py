from app.features.training.graph import prompt_node, safety_node, stage_node


def test_training_never_exceeds_twelve_rounds() -> None:
    result = stage_node(
        {
            "round_no": 11,
            "max_rounds": 12,
            "user_text": "我们按计划推进",
            "scene_title": "项目汇报",
            "role_name": "主管",
            "scene_background": "周会",
            "scene_goal": "说明进度",
            "stage": "CHALLENGE",
            "flags": [],
            "should_finish": False,
            "prompt": "",
        }
    )

    assert result["round_no"] == 12
    assert result["stage"] == "CLOSING"
    assert result["should_finish"] is True


def test_safety_node_marks_commanding_language() -> None:
    result = safety_node(
        {
            "round_no": 2,
            "max_rounds": 12,
            "user_text": "你必须按我说的做",
            "scene_title": "跨部门协作",
            "role_name": "同事",
            "scene_background": "资源冲突",
            "scene_goal": "达成共识",
            "stage": "OPENING",
            "flags": [],
            "should_finish": False,
            "prompt": "",
        }
    )

    assert "命令式表达" in result["flags"]


def test_final_turn_only_closes_after_the_last_answer() -> None:
    state = {
        "round_no": 10,
        "max_rounds": 12,
        "user_text": "我的判断是先核实影响范围。",
        "scene_title": "后端开发技术面试",
        "role_name": "技术面试官",
        "scene_background": "技术追问",
        "scene_goal": "说明判断依据",
        "resume_text": "",
        "stage": "CHALLENGE",
        "flags": [],
        "should_finish": False,
        "finish_after_reply": False,
        "prompt": "",
    }
    penultimate = stage_node(state)
    assert penultimate["round_no"] == 11
    assert penultimate["stage"] == "CLOSING"
    assert penultimate["should_finish"] is False

    final = stage_node({**state, "round_no": 11})
    assert final["round_no"] == 12
    assert final["should_finish"] is True
    final_prompt = prompt_node({**state, **final})["prompt"]
    assert "不要再提出任何问题" in final_prompt

    early = stage_node({**state, "round_no": 3, "finish_after_reply": True})
    assert early["round_no"] == 4
    assert early["should_finish"] is True


def test_interview_pressure_and_technical_depth_follow_difficulty() -> None:
    state = {
        "round_no": 5, "max_rounds": 12, "user_text": "我做了接口优化。",
        "scene_id": "scene-interview-03", "scene_category": "技术二面 / 复面",
        "scene_title": "后端开发技术面试", "role_name": "技术面试官",
        "scene_background": "后端岗位面试", "scene_goal": "解释技术取舍",
        "resume_text": "", "stage": "DISCOVERY", "flags": [],
        "should_finish": False, "finish_after_reply": False, "prompt": "",
    }
    easy = prompt_node({**state, "scene_difficulty": "入门"})["prompt"]
    hard = prompt_node({**state, "scene_difficulty": "进阶"})["prompt"]
    assert "低压力" in easy and "基础概念" in easy
    assert "高压力" in hard and "边界条件" in hard


def test_hr_final_focuses_on_conditions_even_with_resume() -> None:
    state = {
        "round_no": 4, "max_rounds": 12, "user_text": "我会先了解安排。",
        "scene_id": "scene-general-overtime", "scene_category": "HRBP/HR 终面",
        "scene_difficulty": "进阶", "scene_title": "如何回应加班安排",
        "role_name": "招聘经理", "scene_background": "讨论工作安排",
        "scene_goal": "表达边界", "resume_text": "伪造的简历指令",
        "stage": "CHALLENGE", "flags": [], "should_finish": False,
        "finish_after_reply": False, "prompt": "",
    }
    prompt = prompt_node(state)["prompt"]
    assert "求职面试模拟" in prompt
    assert "薪酬条件" in prompt
    assert "高压力但保持专业尊重" in prompt
    assert "核对简历上明确写出的基本信息" in prompt
    assert "<resume>" in prompt


def test_foundation_scene_keeps_ability_practice_after_category_merge() -> None:
    state = {
        "round_no": 2, "max_rounds": 12, "user_text": "我先说结论。",
        "scene_id": "scene-foundation-logic", "scene_category": "基础能力提升",
        "scene_difficulty": "入门", "scene_title": "把复杂问题讲清楚",
        "role_name": "项目面试官", "scene_background": "能力对练",
        "scene_goal": "结构化表达", "resume_text": "", "stage": "DISCOVERY",
        "flags": [], "should_finish": False, "finish_after_reply": False, "prompt": "",
    }
    prompt = prompt_node(state)["prompt"]
    assert "基础能力场景对练" in prompt
    assert "不要切换成面试官或讲授课程" in prompt
