from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.domain.models import User
from app.infra import db
from app.repositories import conversations as conv_repo
from app.services import chatbot, memory_short

router = APIRouter(prefix="/chat")


class ChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


@router.post("/stream")
async def stream_chat(
    req: ChatRequest,
    session: AsyncSession = Depends(db.get_session),
    current_user: User = Depends(get_current_user),
):
    # Create conversation on first message
    if req.conversation_id is None:
        conv = await conv_repo.create(session, user_id=current_user.id)
        await session.commit()
        conversation_id = conv.id
    else:
        conversation_id = req.conversation_id

    async def event_stream():
        import json

        # First event: tell the client which conversation_id to use
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': str(conversation_id)})}\n\n"
        async for chunk in chatbot.stream_response(
            session=session,
            user_id=current_user.id,
            conversation_id=conversation_id,
            user_message=req.message,
        ):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get(
    "/conversations/{conversation_id}/messages", response_model=list[MessageOut]
)
async def get_messages(
    conversation_id: UUID,
    session: AsyncSession = Depends(db.get_session),
    current_user: User = Depends(get_current_user),
):
    conv = await conv_repo.get(session, conversation_id)
    if conv is None or conv.user_id != current_user.id:
        from app.domain.exceptions import NotFoundError

        raise NotFoundError("Conversation not found")

    # Try Redis first (fast path for active sessions); fall back to Postgres
    redis_history = await memory_short.get_history(conversation_id)
    if redis_history:
        return [
            MessageOut(
                id="",
                role=m["role"],
                content=m["content"],
                created_at="",
            )
            for m in redis_history
        ]

    messages = await conv_repo.get_messages(session, conversation_id)
    return [
        MessageOut(
            id=str(m.id),
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]
