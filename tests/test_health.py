"""
Tests for health check endpoints.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_liveness():
    """Test liveness health check."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "eventbridge"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


def test_health_readiness():
    """Test readiness health check."""
    r = client.get("/health/ready")
    # Should be 200 (ready) or 503 (not ready)
    assert r.status_code in [200, 503]
    data = r.json()
    assert data["service"] == "eventbridge"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert "checks" in data
    assert "status" in data


def test_metrics_endpoint():
    """Test Prometheus metrics endpoint."""
    r = client.get("/metrics")
    assert r.status_code == 200
    # Check for expected metrics
    content = r.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    assert "app_up" in content
    assert "eventbridge_events_published_total" in content


def test_correlation_id_in_response():
    """Test that correlation ID is added to response headers."""
    r = client.get("/health")
    assert "x-correlation-id" in r.headers


def test_correlation_id_propagation():
    """Test that provided correlation ID is propagated."""
    correlation_id = "test-correlation-id-123"
    r = client.get("/health", headers={"x-correlation-id": correlation_id})
    assert r.headers["x-correlation-id"] == correlation_id
