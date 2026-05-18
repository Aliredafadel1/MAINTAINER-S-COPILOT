from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Widget


async def create(
    session: AsyncSession,
    owner_id: UUID,
    name: str,
    allowed_origins: list[str],
    config: dict,
) -> Widget:
    widget = Widget(
        owner_id=owner_id, name=name, allowed_origins=allowed_origins, config=config
    )
    session.add(widget)
    await session.flush()
    await session.refresh(widget)
    return widget


async def get(session: AsyncSession, widget_id: UUID) -> Widget | None:
    return await session.get(Widget, widget_id)


async def list_for_owner(session: AsyncSession, owner_id: UUID) -> list[Widget]:
    result = await session.execute(
        select(Widget)
        .where(Widget.owner_id == owner_id)
        .order_by(Widget.created_at.desc())
    )
    return list(result.scalars())


async def update_origins(
    session: AsyncSession, widget_id: UUID, allowed_origins: list[str]
) -> Widget | None:
    widget = await session.get(Widget, widget_id)
    if widget is None:
        return None
    widget.allowed_origins = allowed_origins
    await session.flush()
    return widget


async def deactivate(session: AsyncSession, widget_id: UUID) -> bool:
    widget = await session.get(Widget, widget_id)
    if widget is None:
        return False
    widget.is_active = False
    return True
