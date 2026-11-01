import asyncio

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Course

COURSES = [
    {
        "title": "把薪资谈判讲成价值对话",
        "dimension": "感染力",
        "minutes": 18,
        "description": "适用于薪资、涨幅、offer 条件等需要说服对方的场景。",
        "content": (
            "先锚定对方关心的问题；用可核对的事实替代形容词；给出区间而不是单点；"
            "把诉求与对方收益绑定；明确下一步与时间点。"
        ),
    },
    {
        "title": "离职原因的稳妥说法",
        "dimension": "得体性",
        "minutes": 15,
        "description": "适用于解释离职动机、空窗期、跳槽频率等敏感问题。",
        "content": (
            "先说客观事实再说主观选择；不评价前东家；把离职原因指向成长方向；"
            "主动给出稳定性证据；对追问说明边界。"
        ),
    },
    {
        "title": "故障复盘的结构化表达",
        "dimension": "逻辑性",
        "minutes": 16,
        "description": "适用于线上问题复盘、事故说明、技术方案取舍。",
        "content": (
            "先给结论与影响面；按时间线还原关键节点；区分直接原因与根因；"
            "给出验证方式与防复发措施；明确责任边界。"
        ),
    },
]


async def main() -> None:
    async with session_factory() as session:
        added = 0
        for item in COURSES:
            exists = await session.scalar(select(Course).where(Course.title == item["title"]))
            if exists:
                continue
            session.add(Course(**item, active=True))
            added += 1
        await session.commit()
        rows = (await session.scalars(select(Course))).all()
        by_dimension: dict[str, int] = {}
        for row in rows:
            by_dimension[row.dimension] = by_dimension.get(row.dimension, 0) + 1
        print(f"added={added} total={len(rows)}", by_dimension)


asyncio.run(main())
