from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.embeddings import embed
from app.repositories import audit as audit_repo
from app.repositories import memories as mem_repo


async def save(
    session: AsyncSession,
    user_id: UUID,
    content: str,
    memory_type: str = "semantic",
    metadata: dict | None = None,
) -> None:
    vec = await embed(content)
    mem = await mem_repo.create(
        session,
        user_id=user_id,
        content=content,
        embedding=vec,
        memory_type=memory_type,
        metadata=metadata,
    )
    await audit_repo.log(
        session,
        action="memory_write",
        user_id=user_id,
        resource_type="memory",
        resource_id=str(mem.id),
        details={"type": memory_type},
    )


async def recall(
    session: AsyncSession, user_id: UUID, query: str, top_k: int = 5
) -> list[str]:
    vec = await embed(query)
    results = await mem_repo.search_similar(
        session, user_id=user_id, embedding=vec, top_k=top_k
    )
    return [m.content for m in results]
