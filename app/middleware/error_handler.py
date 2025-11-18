"""Structured error response middleware."""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from .correlation import get_correlation_id

log = structlog.get_logger()


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Provides structured error responses for all exceptions."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as exc:
            correlation_id = get_correlation_id()
            log.warning(
                "http.exception",
                status_code=exc.status_code,
                detail=exc.detail,
                path=request.url.path,
                correlation_id=correlation_id
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.__class__.__name__,
                    "message": exc.detail,
                    "status_code": exc.status_code,
                    "correlation_id": correlation_id,
                    "path": str(request.url.path)
                }
            )
        except Exception as exc:
            correlation_id = get_correlation_id()
            log.error(
                "unhandled.exception",
                error=str(exc),
                error_type=exc.__class__.__name__,
                path=request.url.path,
                correlation_id=correlation_id,
                exc_info=True
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred",
                    "correlation_id": correlation_id,
                    "path": str(request.url.path)
                }
            )
