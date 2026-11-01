import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import session_factory
from app.db.models import Evaluation, EvaluationEvidence, Message, Scene, TrainingSession, User

random.seed(20261029)

STUDENTS = [
    ("陈雨桐", "chenyutong@example.com"),
    ("李昊然", "liran@example.com"),
    ("周可欣", "zhoukexin@example.com"),
    ("赵子豪", "zhaozihao@example.com"),
]

ANSWERS = [
    "我在上一家公司负责支付链路的稳定性，主要做了三件事：梳理核心接口的超时阈值、补上幂等校验、把告警按影响面分级。",
    "然后就是按计划推进，其实也没想太多，那个事情主要还是看运气吧。",
    "我的结论是先修数据一致性问题：本周有 12 笔订单对账不平，我先补对账脚本，再把写入改成事务，明天验证结果。",
    "这个项目里我负责接口设计，具体实现是同事做的，我就参与了评审。",
    "如果是我的话，会先确认对方最关心的指标，再给两种方案和各自的代价，让对方选。",
]


def scores_for(round_index: int) -> dict:
    base = 40 + round_index * 6 + random.randint(-3, 3)
    return {
        "logic": min(5, max(1, 2 + round_index // 2)),
        "appropriateness": min(5, max(1, 3 + round_index // 3)),
        "impact": min(5, max(1, 2 + round_index // 2)),
        "relevance": min(5, max(1, 3 + round_index // 3)),
        "concision": min(5, max(1, 3 + round_index // 4)),
        "overall": float(min(96, max(28, base))),
    }


async def main() -> None:
    async with session_factory() as session:
        scenes = (await session.scalars(select(Scene).where(Scene.category != "基础能力提升"))).all()
        if not scenes:
            print("no scenes")
            return
        created = 0
        for index, (name, email) in enumerate(STUDENTS):
            existing = await session.scalar(select(User).where(User.email == email))
            if existing:
                continue
            user = User(
                email=email,
                password_hash=hash_password("Student123!"),
                display_name=name,
                role="STUDENT",
                active=True,
                bio=None,
            )
            session.add(user)
            await session.flush()

            rounds_total = 4 + index
            for round_index in range(rounds_total):
                scene = scenes[(index * 3 + round_index) % len(scenes)]
                started = datetime.now(timezone.utc) - timedelta(days=(rounds_total - round_index) * 7 + index)
                training = TrainingSession(
                    user_id=user.id,
                    scene_id=scene.id,
                    status="FINISHED",
                    stage="CLOSING",
                    current_round=6,
                    max_rounds=12,
                    started_at=started,
                    finished_at=started + timedelta(minutes=32),
                    covered_count=5,
                )
                session.add(training)
                await session.flush()

                messages = [Message(session_id=training.id, round_no=0, speaker="AI", content=scene.opening_line)]
                for round_no in range(1, 7):
                    messages.append(Message(
                        session_id=training.id, round_no=round_no, speaker="AI",
                        content=f"第 {round_no} 轮追问：能具体说说你的判断依据吗？",
                    ))
                    answer = ANSWERS[(round_no + index) % len(ANSWERS)]
                    messages.append(Message(
                        session_id=training.id, round_no=round_no, speaker="USER",
                        content=answer,
                        flagged=round_no == 2,
                        flags=["绝对化表达"] if round_no == 2 else [],
                    ))
                session.add_all(messages)
                await session.flush()

                score = scores_for(round_index)
                evaluation = Evaluation(
                    session_id=training.id,
                    user_id=user.id,
                    logic_score=score["logic"],
                    appropriateness_score=score["appropriateness"],
                    impact_score=score["impact"],
                    relevance_score=score["relevance"],
                    concision_score=score["concision"],
                    overall_score=score["overall"],
                    summary="结论基本清楚，但依据偏薄，遇到追问时缺少可核对的数据。",
                    suggestions=[{
                        "roundNo": 1,
                        "problem": "只给了结论，缺少可核对的数据",
                        "original": ANSWERS[0],
                        "rewrite": "我在上一家公司负责支付链路稳定性，把超时接口从 12 个收敛到 5 个，线上超时率下降 60%。",
                        "reference": "我负责支付链路的稳定性：先梳理 12 个核心接口的超时阈值，给写接口补上幂等键，再把告警按影响面分级。三个月后线上超时率从 3% 降到 1.2%。",
                    }],
                    style_tags=["务实", "直接"],
                    speech_stats={
                        "totalChars": 320,
                        "rounds": 6,
                        "fillerTotal": 7,
                        "fillerRate": 0.022,
                        "avgSentenceLength": 21.5,
                        "avgRoundLength": 53.3,
                        "topFillers": [{"word": "然后", "count": 4}, {"word": "就是", "count": 2}, {"word": "其实", "count": 1}],
                    },
                    degraded=False,
                    created_at=started + timedelta(minutes=33),
                )
                session.add(evaluation)
                await session.flush()

                user_messages = [m for m in messages if m.speaker == "USER"]
                for position, dimension in enumerate(["logic", "appropriateness", "impact", "relevance", "concision"]):
                    answer = user_messages[position % len(user_messages)]
                    session.add(EvaluationEvidence(
                        evaluation_id=evaluation.id,
                        dimension=dimension,
                        round_no=answer.round_no,
                        question_message_id=next(m.id for m in messages if m.speaker == "AI" and m.round_no == answer.round_no) if any(m.speaker == "AI" and m.round_no == answer.round_no for m in messages) else messages[0].id,
                        answer_message_id=answer.id,
                        quote=answer.content[:20],
                        reason="该轮回答停留在结论层，缺少可核对的依据。",
                        next_action="每轮结论后补一条可核对的事实或数据。",
                        resume_quote=None,
                    ))
                created += 1
        await session.commit()
        print(f"seeded students={len(STUDENTS)} sessions={created}")


asyncio.run(main())
