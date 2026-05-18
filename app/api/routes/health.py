from fastapi import APIRouter
from app.infra import redis_client, tracing

router = APIRouter()


@router.get("/health")
async def health():
    await redis_client.client().ping()
    return {"status": "ok", "trace_id": tracing.current_trace_id()}
