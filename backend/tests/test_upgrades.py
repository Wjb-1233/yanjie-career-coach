"""措辞升级的规则兜底与校验测试。"""

from app.features.evaluations.service import fallback_upgrades


class Msg:
    def __init__(self, content: str) -> None:
        self.content = content


def test_fallback_upgrades_detects_weak_verb() -> None:
    rows = fallback_upgrades([Msg("我负责了订单系统的开发")])
    assert rows
    assert rows[0]["type"] == "动词升级"
    assert "主导" in rows[0]["improved"]


def test_fallback_upgrades_detects_filler() -> None:
    rows = fallback_upgrades([Msg("然后我做了压测，就是看瓶颈在哪")])
    assert any(row["type"] == "去口语化" for row in rows)


def test_fallback_upgrades_limits_four() -> None:
    messages = [Msg(f"我负责了第{i}个项目，然后上线了") for i in range(6)]
    assert len(fallback_upgrades(messages)) <= 4
