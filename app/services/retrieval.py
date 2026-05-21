from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra import embeddings, llm, minio_client
from app.infra.redaction import redact
from app.infra.tracing import span

_REWRITE_PROMPT = (
    Path(__file__).parent.parent.parent / "prompts" / "rewrite_query.txt"
).read_text


@dataclass
class ChunkResult:
    id: str
    content: str
    source_type: str
    source_id: str
    chunk_index: int
    metadata: dict
    score: float


async def _rewrite_query(query: str) -> str:
    """LLM rewrites the query to be retrieval-friendly."""
    prompt = _REWRITE_PROMPT().replace("{{query}}", query)
    return await llm.complete(prompt, max_tokens=128)


async def _dense_search(
    session: AsyncSession,
    query_vec: list[float],
    top_k: int,
    source_type: str | None,
) -> list[ChunkResult]:
    params: dict = {"vec": str(query_vec), "k": top_k}
    filter_clause = ""
    if source_type:
        filter_clause = "AND source_type = :source_type"
        params["source_type"] = source_type

    rows = await session.execute(
        text(f"""
            SELECT id::text, content, source_type, source_id, chunk_index, metadata,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM corpus_chunks
            WHERE embedding IS NOT NULL
            {filter_clause}
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
        """),
        params,
    )
    return [
        ChunkResult(
            id=r.id,
            content=r.content,
            source_type=r.source_type,
            source_id=r.source_id,
            chunk_index=r.chunk_index,
            metadata=r.metadata or {},
            score=float(r.score),
        )
        for r in rows
    ]


async def _sparse_search(
    session: AsyncSession,
    query: str,
    top_k: int,
    source_type: str | None,
) -> list[ChunkResult]:
    params: dict = {"query": query, "k": top_k}
    filter_clause = ""
    if source_type:
        filter_clause = "AND source_type = :source_type"
        params["source_type"] = source_type

    rows = await session.execute(
        text(f"""
            SELECT id::text, content, source_type, source_id, chunk_index, metadata,
                   ts_rank(content_tsv, plainto_tsquery('english', :query)) AS score
            FROM corpus_chunks
            WHERE content_tsv @@ plainto_tsquery('english', :query)
            {filter_clause}
            ORDER BY score DESC
            LIMIT :k
        """),
        params,
    )
    return [
        ChunkResult(
            id=r.id,
            content=r.content,
            source_type=r.source_type,
            source_id=r.source_id,
            chunk_index=r.chunk_index,
            metadata=r.metadata or {},
            score=float(r.score),
        )
        for r in rows
    ]


def _rrf(lists: list[list[ChunkResult]], k: int = 60) -> list[ChunkResult]:
    """Reciprocal Rank Fusion. k=60 is the standard constant."""
    scores: dict[str, float] = {}
    chunks: dict[str, ChunkResult] = {}
    for result_list in lists:
        for rank, chunk in enumerate(result_list):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
            chunks[chunk.id] = chunk
    ranked = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    for cid in ranked:
        chunks[cid].score = scores[cid]
    return [chunks[cid] for cid in ranked]


async def search(
    session: AsyncSession,
    query: str,
    top_k: int = 5,
    source_type: str | None = None,
    rewrite: bool = True,
) -> list[ChunkResult]:
    """
    Full retrieval pipeline:
    1. Query rewriting (optional)
    2. Embed rewritten query
    3. Dense + sparse search
    4. RRF fusion
    5. Cross-encoder reranking
    """
    with span("retrieval.search", query=redact(query), top_k=top_k):
        retrieval_query = query
        if rewrite:
            with span("retrieval.rewrite"):
                try:
                    retrieval_query = await _rewrite_query(query)
                except Exception:
                    pass  # fall back to original query if LLM unavailable

        with span("retrieval.embed"):
            try:
                query_vec = await embeddings.embed(retrieval_query)
            except Exception:
                return []  # no embeddings = no dense results, return early

        fetch_k = max(top_k * 4, 20)  # fetch more, rerank down to top_k

        dense, sparse = (
            await _dense_search(session, query_vec, fetch_k, source_type),
            await _sparse_search(session, retrieval_query, fetch_k, source_type),
        )

        fused = _rrf([dense, sparse])[:fetch_k]

        if not fused:
            return []

        with span("retrieval.rerank", candidates=len(fused)):
            passages = [c.content for c in fused]
            try:
                scores = await embeddings.rerank(retrieval_query, passages)
                for chunk, score in zip(fused, scores):
                    chunk.score = score
            except Exception:
                pass  # keep original scores if reranker unavailable

        fused.sort(key=lambda c: c.score, reverse=True)
        results = fused[:top_k]

        # Persist snapshot to MinIO for auditability (fire-and-forget)
        try:
            snapshot = {
                "query": redact(query),
                "rewritten_query": redact(retrieval_query),
                "timestamp": time.time(),
                "results": [
                    {
                        "id": c.id,
                        "source_type": c.source_type,
                        "source_id": c.source_id,
                        "chunk_index": c.chunk_index,
                        "score": c.score,
                        "content_preview": c.content[:200],
                    }
                    for c in results
                ],
            }
            key = f"{int(time.time() * 1000)}.json"
            minio_client.put_bytes(
                "rag-snapshots", key, json.dumps(snapshot).encode(), "application/json"
            )
        except Exception:
            pass  # never block retrieval on MinIO failure

        return results
