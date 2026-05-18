from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class RerankRequest(BaseModel):
    query: str
    passages: list[str]


class RerankResponse(BaseModel):
    scores: list[float]


@router.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest, request: Request):
    cross_encoder = request.app.state.cross_encoder
    pairs = [[req.query, p] for p in req.passages]
    scores = cross_encoder.predict(pairs, show_progress_bar=False).tolist()
    return RerankResponse(scores=scores)
