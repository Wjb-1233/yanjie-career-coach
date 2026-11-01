from typing import Literal


SceneCategory = Literal[
    "HR 初面", "技术一面", "技术二面 / 复面", "交叉面 / 总监面",
    "HRBP/HR 终面", "大老板 / 高管终面",
]
SceneDifficulty = Literal["入门", "中级", "进阶"]

LEGACY_CATEGORIES: dict[str, SceneCategory] = {
    "行为面试": "HR 初面",
    "压力面试": "交叉面 / 总监面",
    "技术面试": "技术一面",
    "传统面试": "HR 初面",
    "通用沟通": "HR 初面",
    "薪资沟通": "HRBP/HR 终面",
}

DIMENSION_LABELS = ["逻辑性", "得体性", "正确性", "针对性", "简洁度"]


def normalize_bank(raw):
    """把历史字符串题库与新的对象题库统一成 [{text, dimension, difficulty}]。"""
    result = []
    for item in raw or []:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append({"text": text, "dimension": None, "difficulty": None})
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if text:
                result.append(
                    {
                        "text": text,
                        "dimension": item.get("dimension") or None,
                        "difficulty": item.get("difficulty") or None,
                    }
                )
    return result
