from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from memory_with_receipts.api.routes.health import router as health_router
from memory_with_receipts.core.config import Settings
from memory_with_receipts.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Small request logger. Keep it boring and useful."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        logger.info(
            "request_finished",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
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

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app
