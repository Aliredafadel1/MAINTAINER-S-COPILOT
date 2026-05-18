"""Chatbot: Anthropic tool-calling loop + SSE streaming final answer."""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra import vault
from app.repositories import conversations as conv_repo
from app.services import memory_long, memory_short, tools

_SYSTEM_PROMPT: str | None = None
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOOL_ROUNDS = 5


def _system() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        path = Path("prompts/system.txt")
        _SYSTEM_PROMPT = path.read_text(encoding="utf-8") if path.exists() else ""
    return _SYSTEM_PROMPT


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=vault.get("LLM_API_KEY"))


async def stream_response(
    session: AsyncSession,
    user_id: UUID,
    conversation_id: UUID,
    user_message: str,
) -> AsyncIterator[str]:
    """Yields SSE data lines. Runs tool loop, then streams final answer."""
    # 1. Persist user message
    await conv_repo.add_message(session, conversation_id, "user", user_message)
    await memory_short.append_message(conversation_id, "user", user_message)
    await session.commit()

    # 2. Recall relevant long-term memory to inject into context
    memories = await memory_long.recall(session, user_id, user_message, top_k=3)
    memory_block = ""
    if memories:
        memory_block = "\n\nRelevant memories:\n" + "\n".join(
            f"- {m}" for m in memories
        )

    # 3. Build message history from Redis (fast path)
    history = await memory_short.get_history(conversation_id)
    # Inject memory block as a system note before current turn
    messages: list[dict] = [
        m for m in history[:-1]
    ]  # exclude the just-appended user msg
    if memory_block:
        messages = [
            {"role": "user", "content": memory_block + "\n[acknowledged]"},
            {"role": "assistant", "content": "[Noted the above context.]"},
        ] + messages
    messages.append({"role": "user", "content": user_message})

    client = _client()
    tool_defs = tools.tool_definitions()

    # 4. Tool-calling loop
    for _ in range(_MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=_system(),
            tools=tool_defs,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            # Extract text from final response
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            break

        if response.stop_reason == "tool_use":
            # Execute all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await tools.dispatch(
                        block.name, block.input, session, user_id
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason — treat content as final
        final_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                final_text += block.text
        break
    else:
        final_text = "I reached the tool call limit. Please rephrase your question."

    # 5. Stream final answer via SSE in 20-char chunks
    chunk_size = 20
    for i in range(0, len(final_text), chunk_size):
        chunk = final_text[i : i + chunk_size]
        yield f"data: {json.dumps({'type': 'text', 'text': chunk})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # 6. Persist assistant message
    await conv_repo.add_message(session, conversation_id, "assistant", final_text)
    await memory_short.append_message(conversation_id, "assistant", final_text)
    await session.commit()
