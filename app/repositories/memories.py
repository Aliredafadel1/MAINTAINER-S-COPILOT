from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Memory


async def create(
    session: AsyncSession,
    user_id: UUID,
    content: str,
    embedding: list[float],
    memory_type: str = "semantic",
    metadata: dict | None = None,
) -> Memory:
    mem = Memory(
        user_id=user_id,
        content=content,
        embedding=embedding,
        memory_type=memory_type,
        metadata_=metadata or {},
    )
    session.add(mem)
    await session.flush()
    await session.refresh(mem)
    return mem


async def search_similar(
    session: AsyncSession,
    user_id: UUID,
    embedding: list[float],
    top_k: int = 5,
) -> list[Memory]:
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import cast

    result = await session.execute(
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(
            Memory.embedding.cosine_distance(cast(embedding, Vector(len(embedding))))
        )
        .limit(top_k)
    )
    return list(result.scalars())


async def list_for_user(
    session: AsyncSession, user_id: UUID, limit: int = 50
) -> list[Memory]:
    result = await session.execute(
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def delete(session: AsyncSession, memory_id: UUID, user_id: UUID) -> bool:
    mem = await session.get(Memory, memory_id)
    if mem is None or mem.user_id != user_id:
        return False
    await session.delete(mem)
    return True
