from __future__ import annotations

import uuid

import structlog.contextvars
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from memory_with_receipts.api.routes.ask import router as ask_router
from memory_with_receipts.api.routes.health import router as health_router
from memory_with_receipts.api.routes.operational_memory import router as operational_memory_router
from memory_with_receipts.api.routes.search import router as search_router
from memory_with_receipts.core.config import Settings
from memory_with_receipts.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Small request logger with correlation IDs. Keep it boring and useful."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        logger.info(
            "request_started",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
            )
            raise
        response.headers["x-correlation-id"] = correlation_id
        logger.info(
            "request_finished",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        structlog.contextvars.clear_contextvars()
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application.

    App factory keeps tests simple and avoids global startup side effects.
    """
    app_settings = settings or Settings()
    configure_logging(app_settings.log_level)

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description="Memory system with provenance, receipts, and reliability metadata.",
    )
    app.state.settings = app_settings
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(health_router)
    app.include_router(operational_memory_router)
    app.include_router(search_router)
    app.include_router(ask_router)

    # Lazy-init services and RAG session factory on first use
    # Tests override these via app.state or dependency_overrides
    app.state.search_service = None
    app.state.rag_session_factory = None
    app.state.generation_service = None
    app.state.llm_provider = None

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        logger.warning(
            "request_validation_failed",
            correlation_id=correlation_id,
            path=request.url.path,
            errors=exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "error": "request_validation_failed",
                    "correlation_id": correlation_id,
                    "fields": exc.errors(),
                }
            },
            headers={"x-correlation-id": correlation_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        logger.exception(
            "unhandled_exception",
            correlation_id=correlation_id,
            path=request.url.path,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "error": "internal_server_error",
                    "message": "Internal server error",
                    "correlation_id": correlation_id,
                }
            },
            headers={"x-correlation-id": correlation_id},
        )

    return app
