import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.infra import vault

_engine = None
_session_factory = None


def build_url() -> str:
    password = vault.get("DB_PASSWORD")
    host = os.environ["DB_HOST"]
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def init() -> None:
    global _engine, _session_factory
    url = build_url()
    _engine = create_async_engine(url, pool_size=10, max_overflow=5, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    assert _session_factory is not None, "call init() first"
    async with _session_factory() as session:
        yield session


class Base(DeclarativeBase):
    pass
