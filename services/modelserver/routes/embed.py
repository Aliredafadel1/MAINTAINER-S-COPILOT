from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    embedding: list[float]


class EmbedBatchRequest(BaseModel):
    texts: list[str]


class EmbedBatchResponse(BaseModel):
    embeddings: list[list[float]]


@router.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest, request: Request):
    model = request.app.state.embed_model
    vec = model.encode([req.text], normalize_embeddings=True)[0].tolist()
    return EmbedResponse(embedding=vec)


@router.post("/embed/batch", response_model=EmbedBatchResponse)
def embed_batch(req: EmbedBatchRequest, request: Request):
    model = request.app.state.embed_model
    vecs = model.encode(req.texts, normalize_embeddings=True, batch_size=64).tolist()
    return EmbedBatchResponse(embeddings=vecs)
