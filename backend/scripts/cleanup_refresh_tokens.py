"""清理已过期或已撤销的刷新令牌。"""

import asyncio

from app.db.base import session_factory
from app.features.auth.service import prune_refresh_tokens


async def main() -> None:
    async with session_factory() as session:
        removed = await prune_refresh_tokens(session)
        await session.commit()
        print(f"removed={removed}")


asyncio.run(main())
