from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import Conversation, Message


async def create(
    session: AsyncSession, user_id: UUID, title: str | None = None
) -> Conversation:
    conv = Conversation(user_id=user_id, title=title)
    session.add(conv)
    await session.flush()
    await session.refresh(conv)
    return conv


async def get(session: AsyncSession, conversation_id: UUID) -> Conversation | None:
    return await session.get(Conversation, conversation_id)


async def list_for_user(
    session: AsyncSession, user_id: UUID, limit: int = 50
) -> list[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def get_with_messages(
    session: AsyncSession, conversation_id: UUID
) -> Conversation | None:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    return result.scalar_one_or_none()


async def add_message(
    session: AsyncSession,
    conversation_id: UUID,
    role: str,
    content: str,
    tool_calls: dict | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)
    return msg


async def get_messages(
    session: AsyncSession, conversation_id: UUID, limit: int = 100
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars())
