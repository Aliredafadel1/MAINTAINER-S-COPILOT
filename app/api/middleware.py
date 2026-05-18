import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.infra import tracing

logger = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Injects request_id and trace_id into every request and response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        trace_id = tracing.current_trace_id()

        structlog.contextvars.bind_contextvars(request_id=request_id, trace_id=trace_id)

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Trace-Id"] = trace_id

        structlog.contextvars.clear_contextvars()
        return response
