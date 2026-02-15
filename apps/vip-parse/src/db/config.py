import os
from typing import Tuple

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import create_engine
from sqlmodel.ext.asyncio.session import AsyncSession


POOL_SIZE = 5
MAX_OVERFLOW = 10


def _normalize_database_urls(database_url: str) -> Tuple[str, str]:
    """Return async and sync URLs from a single DATABASE_URL value."""
    if not database_url:
        # Keep app bootable for health reporting when DATABASE_URL is missing.
        database_url = "postgresql://invalid:invalid@localhost:5432/vip30"

    normalized = database_url
    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql://", 1)

    if normalized.startswith("postgresql+asyncpg://"):
        async_url = normalized
        sync_url = normalized.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif normalized.startswith("postgresql://"):
        async_url = normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
        sync_url = normalized
    else:
        raise RuntimeError("DATABASE_URL must use postgres:// or postgresql://")

    return async_url, sync_url


_database_url = os.getenv("DATABASE_URL", "")
_async_database_url, _sync_database_url = _normalize_database_urls(_database_url)

async_engine = create_async_engine(
    _async_database_url,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine = create_engine(
    _sync_database_url,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_pre_ping=True,
)
