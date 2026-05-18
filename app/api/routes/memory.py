from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.domain.models import User
from app.infra import db
from app.repositories import memories as mem_repo

router = APIRouter(prefix="/memory")


class MemoryOut(BaseModel):
    id: str
    content: str
    memory_type: str
    created_at: str


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    session: AsyncSession = Depends(db.get_session),
    current_user: User = Depends(get_current_user),
):
    mems = await mem_repo.list_for_user(session, current_user.id)
    return [
        MemoryOut(
            id=str(m.id),
            content=m.content,
            memory_type=m.memory_type,
            created_at=m.created_at.isoformat(),
        )
        for m in mems
    ]


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: UUID,
    session: AsyncSession = Depends(db.get_session),
    current_user: User = Depends(get_current_user),
):
    deleted = await mem_repo.delete(session, memory_id, current_user.id)
    if not deleted:
        from app.domain.exceptions import NotFoundError

        raise NotFoundError("Memory not found")
    await session.commit()
