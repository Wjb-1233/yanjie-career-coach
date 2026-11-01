"""兼容历史数据：把旧维度名称统一成当前叫法。

数据库里 rename 之前生成的评分摘要、建议、微课仍会带「感染力」，
在读取并再次喂给模型前统一替换，避免旧文案扩散到新内容里。
"""

from __future__ import annotations

LEGACY_LABELS = {
    "感染力": "正确性",
    "impact": "correctness",
}


def modernize(value):
    """递归替换字符串里的旧维度名称。"""
    if isinstance(value, str):
        for old, new in LEGACY_LABELS.items():
            if old in value:
                value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [modernize(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            new_key = LEGACY_LABELS.get(key, key)
            result[new_key] = modernize(item)
        return result
    return value
