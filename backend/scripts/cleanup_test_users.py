import asyncio

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import User

PATTERNS = ("phone-qa-", "e2e-")
NAMES = ("手机语音验收", "端到端测试")


def is_test_user(user: User) -> bool:
    email = user.email or ""
    return any(email.startswith(prefix) for prefix in PATTERNS) or (user.display_name or "") in NAMES


async def main() -> None:
    async with session_factory() as session:
        users = (await session.scalars(select(User))).all()
        targets = [user for user in users if is_test_user(user)]
        for user in targets:
            print(f"delete: {user.display_name} <{user.email}>")
            await session.delete(user)
        await session.commit()
        remaining = (await session.scalars(select(User))).all()
        print(f"deleted={len(targets)} remaining={len(remaining)}")
        for user in remaining:
            print(f"  keep: {user.display_name} <{user.email}> {user.role}")


asyncio.run(main())
