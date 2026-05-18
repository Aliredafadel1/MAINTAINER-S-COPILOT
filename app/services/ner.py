import os
import httpx
from app.domain.exceptions import ToolFailure

_MODELSERVER = os.environ.get("MODELSERVER_URL", "http://modelserver:8001")


async def extract_entities(text: str) -> list[dict]:
    """Call the modelserver NER endpoint. Returns a list of entity dicts."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{_MODELSERVER}/ner", json={"text": text})
            resp.raise_for_status()
            return resp.json()["entities"]
    except httpx.HTTPStatusError as exc:
        raise ToolFailure(f"NER service returned {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise ToolFailure(f"NER service unreachable: {exc}") from exc
