import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.middleware import RequestContextMiddleware
from app.api.routes import audit, auth, chat, health, memory, rag, widgets
from app.domain.exceptions import AppError
from app.infra import db, minio_client, redis_client, tracing, vault


def _redact_processor(
    logger: Any, method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    from app.infra.redaction import redact

    event_dict["event"] = redact(str(event_dict.get("event", "")))
    return event_dict


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        _redact_processor,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()


def _boot_checks() -> None:
    """Hard assertions that must pass before serving traffic."""
    import hashlib
    import json

    import yaml

    # 1. Eval thresholds — any zero or missing value is a misconfiguration
    threshold_path = "eval_thresholds.yaml"
    if os.path.exists(threshold_path):
        with open(threshold_path) as f:
            thresholds = yaml.safe_load(f)
        for section, metrics in thresholds.items():
            for name, value in metrics.items():
                if not value:
                    log.error("eval_threshold_disabled", section=section, metric=name)
                    sys.exit(1)

    # 2. Classifier weights — verify model_card.json exists and SHA-256 matches
    model_card_path = "model_card.json"
    if os.path.exists(model_card_path):
        with open(model_card_path) as f:
            card = json.load(f)
        weights_path = card.get("weights_path", "")
        expected_sha = card.get("weights_sha256", "")
        if weights_path and expected_sha:
            if not os.path.exists(weights_path):
                log.error("classifier_weights_missing", path=weights_path)
                sys.exit(1)
            with open(weights_path, "rb") as f:
                actual_sha = hashlib.sha256(f.read()).hexdigest()
            if actual_sha != expected_sha:
                log.error(
                    "classifier_weights_sha256_mismatch",
                    expected=expected_sha[:16],
                    actual=actual_sha[:16],
                )
                sys.exit(1)
            log.info("classifier_weights_verified")


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    log.info("startup_begin")

    # 1. Secrets — must succeed or we exit
    try:
        vault.load_secrets()
        log.info("vault_loaded")
    except Exception as exc:
        log.error("vault_failed", error=str(exc))
        sys.exit(1)

    # 2. Tracing
    tracing.setup("api")
    log.info("tracing_ready")

    # 3. Database
    db.init()
    log.info("db_ready")

    # 4. Redis
    redis_client.init()
    log.info("redis_ready")

    # 5. MinIO
    minio_client.init()
    log.info("minio_ready")

    # 6. Eval threshold guard
    _boot_checks()

    log.info("startup_complete")
    yield
    log.info("shutdown")


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware that reads allowed_origins from the widgets table.

    Origins are cached for 60 s to avoid a DB round-trip on every request.
    Falls back to deny-all if the DB is unavailable.
    """

    _cache: list[str] = []
    _cache_at: float = 0.0
    _TTL = 60.0

    async def _get_allowed_origins(self) -> list[str]:
        now = time.monotonic()
        if now - self._cache_at < self._TTL:
            return self._cache
        try:
            from sqlalchemy import select

            from app.domain.models import Widget

            async for session in db.get_session():
                result = await session.execute(
                    select(Widget.allowed_origins).where(Widget.is_active == True)  # noqa: E712
                )
                origins: list[str] = []
                for (row_origins,) in result:
                    origins.extend(row_origins or [])
                DynamicCORSMiddleware._cache = list(set(origins))
                DynamicCORSMiddleware._cache_at = now
                return DynamicCORSMiddleware._cache
        except Exception:
            pass
        return DynamicCORSMiddleware._cache  # return stale cache on error

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin", "")
        allowed = await self._get_allowed_origins()
        origin_allowed = origin and ("*" in allowed or origin in allowed)

        if request.method == "OPTIONS":
            response = Response(status_code=204)
        else:
            response = await call_next(request)

        if origin_allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type"
            )
        return response


app = FastAPI(title="Maintainer's Copilot", lifespan=lifespan)

app.add_middleware(DynamicCORSMiddleware)
app.add_middleware(RequestContextMiddleware)

app.include_router(health.router)
app.include_router(rag.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(widgets.router)
app.include_router(memory.router)
app.include_router(audit.router)

if os.path.isdir("public"):
    app.mount("/static", StaticFiles(directory="public"), name="static")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    from app.infra.tracing import current_trace_id

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": request.headers.get("X-Request-Id", ""),
            "trace_id": current_trace_id(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "An unexpected error occurred"},
    )
