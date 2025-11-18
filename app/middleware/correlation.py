"""Correlation ID middleware for request tracing."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
import uuid
from contextvars import ContextVar

log = structlog.get_logger()

# Context variable to store correlation ID across async context
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Injects correlation ID into requests and logging context."""

    async def dispatch(self, request: Request, call_next):
        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in context var for logging
        correlation_id_var.set(correlation_id)

        # Add to request state
        request.state.correlation_id = correlation_id

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response


def get_correlation_id() -> str:
    """Get the current correlation ID from context."""
    return correlation_id_var.get()
