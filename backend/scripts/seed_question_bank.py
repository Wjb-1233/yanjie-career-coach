import asyncio

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Scene


def bank_for(scene: Scene) -> list[str]:
    if scene.category == "基础能力提升":
        return [
            f"结合一次真实经历，说明你在「{scene.title}」上最想改进的一点。",
            "讲讲最近一次你意识到自己表达没讲清楚的情况，当时发生了什么？",
            "如果要让同事三句话内听懂你的结论，你会怎么开场？",
            "对方反问细节时，你通常怎么组织补充信息？",
            "复盘一下：这次之后你做了哪些调整？",
        ]
    position = scene.position or "这个岗位"
    return [
        f"先做一个简短的自我介绍，重点讲和{position}相关的经历。",
        f"讲一个你亲自负责过的{position}相关项目，你本人具体做了什么？",
        "这个项目里最关键的一项技术或方法决策是什么，为什么这么选？",
        "过程中遇到过什么问题？你是怎么定位和解决的？",
        "如果重新做一次，你会在哪里改动，为什么？",
    ]


async def main() -> None:
    async with session_factory() as session:
        scenes = (await session.scalars(select(Scene))).all()
        filled = 0
        for scene in scenes:
            if scene.question_bank:
                continue
            scene.question_bank = bank_for(scene)
            filled += 1
        await session.commit()
        print(f"filled={filled} total={len(scenes)}")
        for scene in scenes[:3]:
            print(scene.title, "->", len(scene.question_bank or []))


asyncio.run(main())
