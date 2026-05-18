from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AuditLog


async def log(
    session: AsyncSession,
    action: str,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_recent(
    session: AsyncSession, limit: int = 100, user_id: UUID | None = None
) -> list[AuditLog]:
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if user_id is not None:
        q = q.where(AuditLog.user_id == user_id)
    result = await session.execute(q)
    return list(result.scalars())
