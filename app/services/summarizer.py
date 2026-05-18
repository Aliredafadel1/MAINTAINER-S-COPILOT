import os
import httpx
from app.domain.exceptions import ToolFailure

_MODELSERVER = os.environ.get("MODELSERVER_URL", "http://modelserver:8001")


async def summarize(title: str, body: str, comments: list[str] | None = None) -> str:
    """Call the modelserver summarize endpoint. Returns a 2-4 sentence summary."""
    payload = {"title": title, "body": body, "comments": comments or []}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{_MODELSERVER}/summarize", json=payload)
            resp.raise_for_status()
            return resp.json()["summary"]
    except httpx.HTTPStatusError as exc:
        raise ToolFailure(
            f"Summarizer service returned {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise ToolFailure(f"Summarizer service unreachable: {exc}") from exc
