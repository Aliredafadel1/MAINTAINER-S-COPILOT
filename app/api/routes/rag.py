from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra import db, llm
from app.infra.redaction import redact
from app.infra.tracing import span
from app.services import retrieval

router = APIRouter(prefix="/rag")

RAG_ANSWER_SYSTEM = (
    "You are a helpful assistant for an open-source maintainer. "
    "Answer the question using only the provided context. "
    "If the context does not contain enough information, say so. "
    "Be concise."
)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    source_type: str | None = None


class SearchResult(BaseModel):
    id: str
    content: str
    source_type: str
    source_id: str
    chunk_index: int
    metadata: dict
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]


class AnswerRequest(BaseModel):
    question: str
    context: str


class AnswerResponse(BaseModel):
    answer: str


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, session: AsyncSession = Depends(db.get_session)):
    with span("rag.search", query=redact(req.query), top_k=req.top_k):
        chunks = await retrieval.search(session, req.query, req.top_k, req.source_type)
        return SearchResponse(
            results=[
                SearchResult(
                    id=c.id,
                    content=c.content,
                    source_type=c.source_type,
                    source_id=c.source_id,
                    chunk_index=c.chunk_index,
                    metadata=c.metadata,
                    score=c.score,
                )
                for c in chunks
            ]
        )


@router.post("/answer", response_model=AnswerResponse)
async def answer(req: AnswerRequest):
    prompt = f"Context:\n{req.context}\n\nQuestion: {req.question}"
    with span("rag.answer", question=redact(req.question)):
        text = await llm.complete(prompt, system=RAG_ANSWER_SYSTEM, max_tokens=512)
        return AnswerResponse(answer=text)
