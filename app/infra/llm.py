import time

import anthropic
from app.infra import vault
from app.infra.redaction import redact

_MODEL = "claude-haiku-4-5-20251001"


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=vault.get("LLM_API_KEY"))


async def complete(prompt: str, system: str = "", max_tokens: int = 512) -> str:
    """Single-turn completion with tracing span for model name, tokens, latency."""
    from app.infra.tracing import span

    client = get_client()
    messages = [{"role": "user", "content": prompt}]

    t0 = time.perf_counter()
    with span("llm.complete", model=_MODEL, max_tokens=max_tokens) as s:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            system=system if system else anthropic.NOT_GIVEN,
            messages=messages,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        s.set_attribute("llm.prompt_tokens", response.usage.input_tokens)
        s.set_attribute("llm.completion_tokens", response.usage.output_tokens)
        s.set_attribute("llm.latency_ms", latency_ms)
        s.set_attribute("llm.prompt_preview", redact(prompt[:200]))
        return response.content[0].text.strip()
