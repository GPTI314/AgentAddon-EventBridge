"""
Middleware for observability features.
"""
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation IDs to all requests.

    - Extracts correlation ID from X-Correlation-ID header if present
    - Generates new UUID if not present
    - Binds correlation ID to structlog context
    - Adds correlation ID to response headers
    """

    async def dispatch(self, request: Request, call_next):
        # Get or generate correlation ID
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            http_method=request.method,
            http_path=request.url.path,
        )

        # Process request
        response = await call_next(request)

        # Add correlation ID to response
        response.headers["x-correlation-id"] = correlation_id

        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP metrics for Prometheus.

    - Records request count by method, path, status
    - Records request duration histogram
    - Tracks active requests
    """

    def __init__(self, app, metrics):
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        # Track active requests
        self.metrics.http_requests_active.inc()

        # Record start time
        start_time = time.time()

        # Get logger
        logger = structlog.get_logger()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            self.metrics.http_requests_total.labels(
                service=self.metrics.service_name,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
            ).inc()

            self.metrics.http_request_duration.labels(
                service=self.metrics.service_name,
                method=request.method,
                path=request.url.path,
            ).observe(duration)

            # Log request
            logger.info(
                "http_request",
                http_status=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )

            return response

        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time

            # Record error metrics
            self.metrics.http_requests_total.labels(
                service=self.metrics.service_name,
                method=request.method,
                path=request.url.path,
                status=500,
            ).inc()

            # Log error
            logger.error(
                "http_request_error",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration * 1000, 2),
            )

            raise

        finally:
            # Decrement active requests
            self.metrics.http_requests_active.dec()
