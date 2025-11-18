"""
AgentAddon EventBridge - Event publishing and routing service.

Features:
- Structured logging with correlation IDs
- Prometheus metrics
- Health checks (liveness and readiness)
- Event publishing and retrieval
"""
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from .config import get_settings
from .logging import setup_logging, get_logger
from .api.router import router
from .middleware import CorrelationIdMiddleware, MetricsMiddleware
from .metrics import Metrics
from .health import HealthChecker

# Initialize configuration
settings = get_settings()

# Setup logging
setup_logging(json_output=settings.LOG_JSON, service_name="eventbridge")
logger = get_logger()

# Initialize metrics
metrics = Metrics(service_name="eventbridge", version="0.1.0")

# Initialize health checker
health_checker = HealthChecker(service_name="eventbridge", version="0.1.0")

# Set metrics for event bus
from .services.event_bus import set_metrics
set_metrics(metrics)

# Create FastAPI app
app = FastAPI(
    title="AgentAddon EventBridge",
    version="0.1.0",
    description="Event publishing and routing service with unified observability",
)

# Add middleware (order matters: correlation ID first, then metrics)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(MetricsMiddleware, metrics=metrics)

# Include API routes
app.include_router(router)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app(registry=metrics.registry)
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health():
    """
    Liveness probe - basic health check.

    Returns 200 if service is running.
    """
    logger.debug("health_check_liveness")
    return health_checker.liveness()


@app.get("/health/ready")
async def health_ready():
    """
    Readiness probe - comprehensive health check.

    Checks:
    - Redis connectivity (if configured)
    - Disk space availability
    - Memory availability

    Returns:
        200: Service is ready to handle traffic
        503: Service is not ready
    """
    logger.debug("health_check_readiness")
    result = await health_checker.readiness()

    # Return 503 if not ready
    status_code = 200 if result["status"] == "ready" else 503

    return result, status_code


@app.on_event("startup")
async def startup_event():
    """
    Startup event handler.

    Logs service startup and initializes resources.
    """
    logger.info(
        "service_starting",
        version="0.1.0",
        env=settings.ENV,
        redis_configured=bool(settings.REDIS_URL),
    )


@app.on_event("shutdown")
async def shutdown_event():
    """
    Shutdown event handler.

    Logs service shutdown and cleans up resources.
    """
    logger.info("service_stopping")
    # Set app_up metric to 0
    metrics.app_up.labels(service="eventbridge", version="0.1.0").set(0)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.SERVICE_PORT,
        reload=True,
    )
