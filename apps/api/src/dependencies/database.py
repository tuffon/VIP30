from typing import AsyncGenerator

from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db import async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
