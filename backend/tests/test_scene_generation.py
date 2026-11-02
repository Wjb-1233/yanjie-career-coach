"""场景批量生成的校验逻辑测试（不调用模型）。"""

from scripts.generate_scenes import validate

SAMPLE = {
    "scenes": [
        {
            "title": "转岗动机怎么讲",
            "roleName": "招聘 HR",
            "difficulty": "中级",
            "background": "候选人想从测试转开发。",
            "goal": "说明转岗动机与准备",
            "openingLine": "你为什么想转开发？",
            "tags": ["转岗", "动机"],
            "questionBank": [
                {"text": "你为什么想转开发？", "dimension": "贴合问题", "difficulty": "中级"},
                {"text": "你为转岗做了哪些准备？", "dimension": "信息完整", "difficulty": "中级"},
            ],
        },
        {
            "title": "转岗动机怎么讲",
            "roleName": "HR",
            "difficulty": "中级",
            "background": "重复标题",
            "goal": "x",
            "questionBank": [],
        },
        {"title": "", "roleName": "HR", "difficulty": "中级", "background": "无标题", "goal": "x"},
        {
            "title": "只有一条题",
            "roleName": "HR",
            "difficulty": "未知难度",
            "background": "背景",
            "goal": "目标",
            "openingLine": "",
            "questionBank": [{"text": "唯一的问题？", "dimension": "乱写维度"}],
        },
    ]
}


def test_validate_filters_invalid_and_dedupes() -> None:
    scenes, problems = validate(SAMPLE, set())
    assert len(scenes) == 1
    assert scenes[0]["title"] == "转岗动机怎么讲"
    assert len(problems) == 3  # 重复标题、缺标题、必问题不足


def test_validate_normalizes_fields() -> None:
    scenes, _ = validate(SAMPLE, set())
    scene = scenes[0]
    assert scene["difficulty"] == "中级"
    assert all(item["dimension"] in {"贴近问题", "贴合问题", "信息完整", "内容与逻辑", "表达干净"} for item in scene["question_bank"])
    assert scene["tags"] == ["转岗", "动机"]


def test_validate_keeps_existing_titles_out() -> None:
    scenes, problems = validate(SAMPLE, {"转岗动机怎么讲"})
    assert scenes == []
    assert any("重复" in item for item in problems)


def test_filter_by_scores_drops_low_quality() -> None:
    from scripts.generate_scenes import filter_by_scores

    scenes = [
        {"title": "场景A", "background": "b", "goal": "g", "question_bank": []},
        {"title": "场景B", "background": "b", "goal": "g", "question_bank": []},
        {"title": "场景C", "background": "b", "goal": "g", "question_bank": []},
    ]
    scores = [
        {"index": 1, "realism": 9, "distinctiveness": 8, "answerability": 9},
        {"index": 2, "realism": 9, "distinctiveness": 5, "answerability": 8},
    ]
    kept, dropped = filter_by_scores(scenes, scores)
    assert [scene["title"] for scene in kept] == ["场景A", "场景C"]
    assert any("场景B" in item for item in dropped)


def test_filter_keeps_unscored_scenes() -> None:
    from scripts.generate_scenes import filter_by_scores

    scenes = [{"title": "未打分", "background": "b", "goal": "g", "question_bank": []}]
    kept, dropped = filter_by_scores(scenes, [])
    assert len(kept) == 1
    assert dropped == []
