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
