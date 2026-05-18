import json
from uuid import UUID

from app.infra.redis_client import client as redis

_TTL = 7200  # 2 hours
_PREFIX = "conv:"


def _key(conversation_id: UUID) -> str:
    return f"{_PREFIX}{conversation_id}"


async def get_history(conversation_id: UUID) -> list[dict]:
    raw = await redis().get(_key(conversation_id))
    if raw is None:
        return []
    return json.loads(raw)


async def append_message(conversation_id: UUID, role: str, content: str) -> None:
    key = _key(conversation_id)
    history = await get_history(conversation_id)
    history.append({"role": role, "content": content})
    # Keep last 40 turns to bound token count
    history = history[-40:]
    await redis().setex(key, _TTL, json.dumps(history))


async def clear(conversation_id: UUID) -> None:
    await redis().delete(_key(conversation_id))
