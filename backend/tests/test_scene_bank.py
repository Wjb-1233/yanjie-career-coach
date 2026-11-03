"""题库导出/导入格式的测试。"""

from app.features.scenes.bank import build_bank, scene_to_dict, validate_scene


class FakeScene:
    id = "scene-1"
    category = "HR 初面"
    title = "薪资沟通"
    difficulty = "中级"
    role_name = "招聘 HR"
    background = "背景"
    goal = "目标"
    opening_line = "你好"
    tags = ["薪资"]
    question_bank = [
        {"text": "期望薪资多少？", "dimension": "贴合问题", "difficulty": "中级"},
        {"text": "为什么想要这个数？", "dimension": "内容与逻辑", "difficulty": "中级"},
    ]


def test_scene_to_dict_keeps_questions() -> None:
    data = scene_to_dict(FakeScene())
    assert data["title"] == "薪资沟通"
    assert len(data["questions"]) == 2


def test_build_bank_has_version_and_count() -> None:
    bank = build_bank([FakeScene()])
    assert bank["version"] >= 1
    assert bank["count"] == 1
    assert bank["scenes"][0]["roleName"] == "招聘 HR"


def test_validate_scene_rejects_missing_fields() -> None:
    assert validate_scene({})[0] is None
    assert validate_scene({"title": "无分类"})[0] is None
    scene, problems = validate_scene({"title": "无问题", "category": "HR 初面", "questions": []})
    assert scene is None
    assert problems


def test_validate_scene_normalizes() -> None:
    scene, problems = validate_scene(
        {
            "title": " 转岗动机 ",
            "category": "HR 初面",
            "difficulty": "超难",
            "questions": [{"text": "为什么转岗？", "dimension": "乱写"}],
            "tags": ["a", "b", "c", "d"],
        }
    )
    assert scene is not None
    assert scene["title"] == "转岗动机"
    assert scene["difficulty"] == "中级"
    assert scene["question_bank"][0]["dimension"] is None
    assert len(scene["tags"]) == 3
