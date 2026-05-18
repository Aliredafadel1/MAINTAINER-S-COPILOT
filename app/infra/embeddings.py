import os
import httpx
from app.domain.exceptions import EmbeddingError

_MODELSERVER = os.environ.get("MODELSERVER_URL", "http://modelserver:8001")


async def embed(text: str) -> list[float]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{_MODELSERVER}/embed", json={"text": text})
            resp.raise_for_status()
            return resp.json()["embedding"]
    except httpx.HTTPStatusError as exc:
        raise EmbeddingError(
            f"embed endpoint returned {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise EmbeddingError(f"modelserver unreachable: {exc}") from exc


async def embed_batch(texts: list[str]) -> list[list[float]]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_MODELSERVER}/embed/batch", json={"texts": texts}
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]
    except httpx.HTTPStatusError as exc:
        raise EmbeddingError(
            f"embed/batch endpoint returned {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise EmbeddingError(f"modelserver unreachable: {exc}") from exc


async def rerank(query: str, passages: list[str]) -> list[float]:
    """Returns a score per passage (higher = more relevant)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_MODELSERVER}/rerank",
                json={"query": query, "passages": passages},
            )
            resp.raise_for_status()
            return resp.json()["scores"]
    except httpx.HTTPStatusError as exc:
        raise EmbeddingError(
            f"rerank endpoint returned {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise EmbeddingError(f"modelserver unreachable: {exc}") from exc
