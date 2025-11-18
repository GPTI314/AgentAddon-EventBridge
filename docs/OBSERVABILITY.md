# Unified Observability Standards

This document defines the unified observability standards for all AgentAddon services (EventBridge, VectorHub, SecretGateway).

## Overview

All services implement standardized:
- **Structured Logging** with consistent fields
- **Prometheus Metrics** for monitoring
- **Health Endpoints** for liveness/readiness checks
- **Correlation IDs** for request tracing

## 1. Structured Logging (structlog)

### Standard Log Fields

All log entries MUST include these fields:

```json
{
  "ts": "2025-11-18T04:30:00.123456Z",  // ISO 8601 timestamp
  "level": "info",                       // debug, info, warning, error, critical
  "service": "eventbridge",              // Service name: eventbridge, vectorhub, secretgateway
  "correlation_id": "uuid-v4",           // Request correlation ID
  "event": "message",                    // Log message
  "module": "app.api.router",            // Python module
  "function": "publish_event",           // Function name
  "line": 42                             // Line number
}
```

### Context-Specific Fields

Additional fields based on context:

**HTTP Requests:**
```json
{
  "http_method": "POST",
  "http_path": "/v1/events",
  "http_status": 200,
  "duration_ms": 45.2,
  "client_ip": "192.168.1.1"
}
```

**Business Operations:**
```json
{
  "operation": "event_publish",
  "event_id": "evt_123",
  "event_type": "agent.task.completed"
}
```

**Errors:**
```json
{
  "error": "ValueError: Invalid payload",
  "error_type": "ValueError",
  "stack_trace": "..."
}
```

### Implementation Example

```python
import structlog

logger = structlog.get_logger()

# Bind service-level context
logger = logger.bind(service="eventbridge")

# Log with correlation ID
logger.info(
    "event_published",
    correlation_id=correlation_id,
    event_id=event.id,
    event_type=event.type,
    duration_ms=42.5
)
```

## 2. Prometheus Metrics

### Standard Metrics Endpoint

- **Path:** `/metrics`
- **Format:** Prometheus text format
- **Authentication:** None (internal monitoring network)

### Required Metrics

All services MUST expose:

**HTTP Metrics:**
```
# Request count by endpoint, method, status
http_requests_total{service="eventbridge", method="POST", path="/v1/events", status="200"} 1234

# Request duration histogram (seconds)
http_request_duration_seconds_bucket{service="eventbridge", method="POST", path="/v1/events", le="0.1"} 900
http_request_duration_seconds_sum{service="eventbridge", method="POST", path="/v1/events"} 45.6
http_request_duration_seconds_count{service="eventbridge", method="POST", path="/v1/events"} 1234

# Active requests gauge
http_requests_active{service="eventbridge"} 3
```

**Application Metrics:**
```
# Up/down status
app_up{service="eventbridge", version="0.1.0"} 1

# Business metrics (service-specific)
eventbridge_events_published_total{event_type="agent.task.completed"} 5678
eventbridge_events_active{} 42

vectorhub_documents_stored_total{collection="default"} 10000
vectorhub_search_operations_total{} 567

secretgateway_secrets_accessed_total{secret_type="api_key"} 89
secretgateway_cache_hits_total{} 450
```

**System Metrics:**
```
# Process info
process_cpu_seconds_total{service="eventbridge"} 123.45
process_resident_memory_bytes{service="eventbridge"} 50000000
process_open_fds{service="eventbridge"} 25
```

### Implementation

Use `prometheus_client` library:

```python
from prometheus_client import Counter, Histogram, Gauge, Info, make_asgi_app

# Define metrics
http_requests = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['service', 'method', 'path', 'status']
)

http_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['service', 'method', 'path']
)

# Mount at /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

## 3. Health Endpoints

### /health (Liveness)

Basic liveness check - "is the service running?"

**Response:**
```json
{
  "status": "ok",
  "service": "eventbridge",
  "version": "0.1.0",
  "timestamp": "2025-11-18T04:30:00.123456Z"
}
```

**Status Codes:**
- `200`: Service is alive
- `503`: Service is down

### /health/ready (Readiness)

Readiness check - "can the service handle traffic?"

Checks:
- Database/Redis connectivity
- Downstream service availability
- Resource availability (disk, memory)

**Response (Healthy):**
```json
{
  "status": "ready",
  "service": "eventbridge",
  "version": "0.1.0",
  "timestamp": "2025-11-18T04:30:00.123456Z",
  "checks": {
    "redis": {"status": "ok", "latency_ms": 2.3},
    "disk_space": {"status": "ok", "available_gb": 50.2},
    "memory": {"status": "ok", "available_mb": 1024}
  }
}
```

**Response (Unhealthy):**
```json
{
  "status": "not_ready",
  "service": "eventbridge",
  "version": "0.1.0",
  "timestamp": "2025-11-18T04:30:00.123456Z",
  "checks": {
    "redis": {"status": "error", "error": "Connection timeout"},
    "disk_space": {"status": "ok", "available_gb": 50.2},
    "memory": {"status": "warning", "available_mb": 100}
  }
}
```

**Status Codes:**
- `200`: Service is ready
- `503`: Service is not ready

## 4. Correlation IDs

### Purpose

Track requests across service boundaries for distributed tracing.

### Implementation

**HTTP Headers:**
- Incoming: `X-Correlation-ID` (if present, use it)
- Outgoing: `X-Correlation-ID` (propagate or generate)

**Middleware:**
```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import structlog

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Get or generate correlation ID
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        # Add to response headers
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id

        return response
```

**Usage:**
```python
# Middleware auto-binds correlation_id to logger context
logger.info("processing_request")  # correlation_id included automatically
```

## 5. Log Rotation

### Configuration

All services use `logrotate` for file-based logs (when not shipping directly to log aggregator).

**logrotate.conf example:**
```
/var/log/agentaddon/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 app app
    sharedscripts
    postrotate
        systemctl reload agentaddon-* 2>/dev/null || true
    endscript
}
```

### Docker Logging

When running in containers, use Docker's JSON file driver with rotation:

**docker-compose.yml:**
```yaml
services:
  eventbridge:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 6. Monitoring Dashboard

### Recommended Queries

**Service Health:**
```promql
# Services up
up{job=~"eventbridge|vectorhub|secretgateway"}

# Request rate (req/s)
rate(http_requests_total[5m])

# Error rate (4xx/5xx)
rate(http_requests_total{status=~"4..|5.."}[5m])

# Latency p95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**Cross-Service Correlation:**
```promql
# Total request rate across all services
sum(rate(http_requests_total[5m])) by (service)

# Error rate comparison
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
```

## 7. Implementation Checklist

For each service:

- [ ] Install dependencies: `structlog`, `prometheus-client`
- [ ] Configure structlog with standard processors
- [ ] Add CorrelationIdMiddleware
- [ ] Update logger calls to include context
- [ ] Define Prometheus metrics
- [ ] Create metrics middleware
- [ ] Mount `/metrics` endpoint
- [ ] Enhance `/health` endpoint
- [ ] Add `/health/ready` endpoint
- [ ] Configure log rotation
- [ ] Update documentation
- [ ] Add monitoring examples

## 8. Testing

### Log Format Validation

```python
import json

def test_log_format():
    # Capture log output
    log_entry = json.loads(log_output)

    # Verify required fields
    assert "ts" in log_entry
    assert "level" in log_entry
    assert "service" in log_entry
    assert "correlation_id" in log_entry
    assert "event" in log_entry
```

### Metrics Validation

```python
def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.content
```

### Health Check Validation

```python
def test_health_liveness():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_health_readiness():
    response = client.get("/health/ready")
    assert response.status_code in [200, 503]
    assert "checks" in response.json()
```

## 9. References

- [structlog documentation](https://www.structlog.org/)
- [Prometheus client Python](https://github.com/prometheus/client_python)
- [FastAPI middleware guide](https://fastapi.tiangolo.com/advanced/middleware/)
- [12-Factor App Logs](https://12factor.net/logs)
