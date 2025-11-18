# Observability Implementation Guide

This guide provides step-by-step instructions for implementing unified observability in AgentAddon services (VectorHub, SecretGateway, and any future services).

## Overview

The EventBridge service has been fully instrumented with unified observability. Use it as a reference implementation and follow this guide to apply the same patterns to other services.

## Prerequisites

- Python 3.10+
- FastAPI application
- Existing service structure

## Step 1: Install Dependencies

Add to `requirements.txt`:

```txt
structlog==23.2.0
prometheus-client==0.19.0
psutil==5.9.8
```

## Step 2: Copy Core Modules

Copy these files from EventBridge to your service:

### 2.1 Logging Module (`app/logging.py`)

Copy from: `AgentAddon-EventBridge/app/logging.py`

**Customization needed:**
- Change service name in `add_service_name()` function:
  ```python
  def add_service_name(logger: Any, method_name: str, event_dict: dict) -> dict:
      event_dict["service"] = "vectorhub"  # Change this
      return event_dict
  ```

### 2.2 Middleware Module (`app/middleware.py`)

Copy from: `AgentAddon-EventBridge/app/middleware.py`

**No customization needed** - works as-is.

### 2.3 Metrics Module (`app/metrics.py`)

Copy from: `AgentAddon-EventBridge/app/metrics.py`

**Customization needed:**
- Remove EventBridge-specific metrics
- Add service-specific metrics

**Example for VectorHub:**

```python
# VectorHub-specific metrics
self.documents_stored_total = Counter(
    "vectorhub_documents_stored_total",
    "Total documents stored",
    ["collection"],
    registry=self.registry,
)

self.documents_count = Gauge(
    "vectorhub_documents_count",
    "Current number of documents",
    ["collection"],
    registry=self.registry,
)

self.search_operations_total = Counter(
    "vectorhub_search_operations_total",
    "Total search operations",
    ["collection"],
    registry=self.registry,
)

self.search_duration = Histogram(
    "vectorhub_search_duration_seconds",
    "Search operation duration",
    ["collection"],
    registry=self.registry,
)
```

**Example for SecretGateway:**

```python
# SecretGateway-specific metrics
self.secrets_accessed_total = Counter(
    "secretgateway_secrets_accessed_total",
    "Total secret access operations",
    ["secret_type", "status"],  # status: success, error
    registry=self.registry,
)

self.secrets_cached_total = Gauge(
    "secretgateway_secrets_cached",
    "Number of secrets in cache",
    registry=self.registry,
)

self.cache_hits_total = Counter(
    "secretgateway_cache_hits_total",
    "Cache hit count",
    registry=self.registry,
)

self.cache_misses_total = Counter(
    "secretgateway_cache_misses_total",
    "Cache miss count",
    registry=self.registry,
)

self.secret_access_duration = Histogram(
    "secretgateway_secret_access_duration_seconds",
    "Secret access operation duration",
    ["secret_type"],
    registry=self.registry,
)
```

### 2.4 Health Check Module (`app/health.py`)

Copy from: `AgentAddon-EventBridge/app/health.py`

**Customization needed:**
- Change service name in constructor
- Add service-specific health checks

**Example additions for VectorHub:**

```python
async def _check_vector_db(self) -> Dict[str, Any]:
    """Check vector database connectivity."""
    try:
        # Add your vector DB health check here
        # Example for ChromaDB:
        # client.heartbeat()
        return {"status": "ok"}
    except Exception as e:
        logger.warning("vector_db_health_check_failed", error=str(e))
        return {"status": "error", "error": str(e)}
```

**Example additions for SecretGateway:**

```python
async def _check_secret_backend(self) -> Dict[str, Any]:
    """Check secret backend connectivity."""
    try:
        # Add your secret backend health check here
        # Example: test read from Vault/AWS Secrets Manager
        return {"status": "ok"}
    except Exception as e:
        logger.warning("secret_backend_health_check_failed", error=str(e))
        return {"status": "error", "error": str(e)}
```

## Step 3: Update Main Application

Update `app/main.py`:

```python
"""
AgentAddon [ServiceName] - [Brief description]

Features:
- Structured logging with correlation IDs
- Prometheus metrics
- Health checks (liveness and readiness)
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

# Setup logging (change service_name)
setup_logging(json_output=settings.LOG_JSON, service_name="vectorhub")
logger = get_logger()

# Initialize metrics (change service_name and version)
metrics = Metrics(service_name="vectorhub", version="0.1.0")

# Initialize health checker (change service_name and version)
health_checker = HealthChecker(service_name="vectorhub", version="0.1.0")

# Create FastAPI app
app = FastAPI(
    title="AgentAddon VectorHub",
    version="0.1.0",
    description="Vector database service with unified observability",
)

# Add middleware
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(MetricsMiddleware, metrics=metrics)

# Include API routes
app.include_router(router)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app(registry=metrics.registry)
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health():
    """Liveness probe."""
    logger.debug("health_check_liveness")
    return health_checker.liveness()


@app.get("/health/ready")
async def health_ready():
    """Readiness probe."""
    logger.debug("health_check_readiness")
    result = await health_checker.readiness()
    status_code = 200 if result["status"] == "ready" else 503
    return result, status_code


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info(
        "service_starting",
        version="0.1.0",
        env=settings.ENV,
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("service_stopping")
    metrics.app_up.labels(service="vectorhub", version="0.1.0").set(0)
```

## Step 4: Update API Routes

Update your route handlers to use structured logging:

```python
from ..logging import get_logger

logger = get_logger()

@router.post("/documents")
async def store_document(req: StoreRequest):
    """Store a document in the vector database."""
    logger.info(
        "storing_document",
        collection=req.collection,
        doc_id=req.document_id,
    )

    try:
        # Your business logic here
        result = store_document_impl(req)

        logger.info(
            "document_stored",
            collection=req.collection,
            doc_id=result.id,
        )

        return result

    except Exception as e:
        logger.error(
            "document_store_failed",
            collection=req.collection,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
```

## Step 5: Record Business Metrics

Add metric recording to your business logic:

**VectorHub example:**

```python
# In your document storage logic
metrics.documents_stored_total.labels(collection=collection_name).inc()
metrics.documents_count.labels(collection=collection_name).set(total_docs)

# In your search logic
start = time.time()
results = perform_search(query)
duration = time.time() - start

metrics.search_operations_total.labels(collection=collection_name).inc()
metrics.search_duration.labels(collection=collection_name).observe(duration)
```

**SecretGateway example:**

```python
# In your secret access logic
start = time.time()
try:
    secret = get_secret(secret_name)
    duration = time.time() - start

    metrics.secrets_accessed_total.labels(
        secret_type=secret.type,
        status="success"
    ).inc()
    metrics.secret_access_duration.labels(
        secret_type=secret.type
    ).observe(duration)

    # If from cache
    if from_cache:
        metrics.cache_hits_total.inc()
    else:
        metrics.cache_misses_total.inc()

except Exception as e:
    duration = time.time() - start
    metrics.secrets_accessed_total.labels(
        secret_type=secret_type,
        status="error"
    ).inc()
    raise
```

## Step 6: Update Tests

Create/update `tests/test_health.py`:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_liveness():
    """Test liveness health check."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "vectorhub"  # Change service name
    assert "timestamp" in data


def test_health_readiness():
    """Test readiness health check."""
    r = client.get("/health/ready")
    assert r.status_code in [200, 503]
    data = r.json()
    assert "checks" in data


def test_metrics_endpoint():
    """Test Prometheus metrics endpoint."""
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text


def test_correlation_id():
    """Test correlation ID propagation."""
    correlation_id = "test-123"
    r = client.get("/health", headers={"x-correlation-id": correlation_id})
    assert r.headers["x-correlation-id"] == correlation_id
```

## Step 7: Configuration

Ensure your `.env` file includes:

```bash
LOG_JSON=true  # Set to false for development
ENV=production
```

## Step 8: Documentation

Copy and customize documentation files:

1. Copy `docs/OBSERVABILITY.md` to your service
2. Copy `docs/logrotate.conf` to your service
3. Update service-specific examples

## Step 9: Docker Configuration

If using Docker, update `docker-compose.yml`:

```yaml
services:
  vectorhub:
    # ... other config ...
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    environment:
      - LOG_JSON=true
      - ENV=production
```

## Step 10: Verify Implementation

### 10.1 Run Tests

```bash
pytest tests/test_health.py -v
```

### 10.2 Start Service

```bash
uvicorn app.main:app --reload
```

### 10.3 Check Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Readiness check
curl http://localhost:8080/health/ready

# Metrics
curl http://localhost:8080/metrics

# Test correlation ID
curl -H "X-Correlation-ID: test-123" http://localhost:8080/health
```

### 10.4 Verify Log Format

Check logs include all required fields:

```json
{
  "ts": "2025-11-18T04:30:00.123456Z",
  "level": "info",
  "service": "vectorhub",
  "correlation_id": "uuid-v4",
  "event": "message",
  "module": "app.api.router",
  "function": "store_document",
  "line": 42
}
```

## Checklist

Use this checklist to ensure complete implementation:

- [ ] Dependencies installed (`structlog`, `prometheus-client`, `psutil`)
- [ ] `app/logging.py` copied and service name updated
- [ ] `app/middleware.py` copied
- [ ] `app/metrics.py` copied and customized with service-specific metrics
- [ ] `app/health.py` copied and customized with service-specific checks
- [ ] `app/main.py` updated with middleware and endpoints
- [ ] API routes updated to use structured logging
- [ ] Business metrics recorded in core operations
- [ ] Tests updated for health and metrics endpoints
- [ ] Documentation copied and customized
- [ ] All tests passing
- [ ] All endpoints verified manually
- [ ] Log format verified

## Troubleshooting

### Circular Import Errors

If you get circular import errors with metrics:
- Use dependency injection pattern (see EventBridge `event_bus.py` for example)
- Import metrics only where needed, not at module level

### Metrics Not Appearing

- Check that metrics are registered with the correct registry
- Verify `/metrics` endpoint is mounted correctly
- Check that metrics are being recorded in business logic

### Logs Missing Fields

- Verify `structlog.contextvars.merge_contextvars` is in processors list
- Check that middleware is added before routes
- Ensure logger is obtained via `get_logger()` function

### Health Checks Failing

- Check that health check dependencies (Redis, DBs) are accessible
- Review health check logs for specific errors
- Verify thresholds (disk, memory) are appropriate for environment

## References

- EventBridge reference implementation: `AgentAddon-EventBridge/`
- Unified observability standards: `docs/OBSERVABILITY.md`
- structlog documentation: https://www.structlog.org/
- Prometheus client: https://github.com/prometheus/client_python
