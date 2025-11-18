"""Tests for middleware components."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import get_settings

settings = get_settings()

@pytest.mark.asyncio
async def test_correlation_id_injection():
    """Test that correlation ID is auto-generated if not provided."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            json={"source": "test", "type": "test.event", "payload": {"foo": "bar"}}
        )
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        data = response.json()
        assert data["correlation_id"] is not None


@pytest.mark.asyncio
async def test_correlation_id_preserved():
    """Test that provided correlation ID is preserved."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        correlation_id = "test-correlation-123"
        response = await client.post(
            "/v1/events",
            json={"source": "test", "type": "test.event", "payload": {"foo": "bar"}},
            headers={"X-Correlation-ID": correlation_id}
        )
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == correlation_id


@pytest.mark.asyncio
async def test_payload_too_large_rejection():
    """Test that oversized payloads are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a payload larger than MAX_EVENT_SIZE (65536 bytes)
        large_payload = {"data": "x" * (settings.MAX_EVENT_SIZE + 1000)}
        response = await client.post(
            "/v1/events",
            json={"source": "test", "type": "test.event", "payload": large_payload}
        )
        assert response.status_code == 413
        data = response.json()
        assert data["error"] == "PayloadTooLarge"
        assert "max_size" in data
        assert data["max_size"] == settings.MAX_EVENT_SIZE


@pytest.mark.asyncio
async def test_invalid_json_rejection():
    """Test that invalid JSON is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            content=b"{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "InvalidJSON"


@pytest.mark.asyncio
async def test_missing_required_fields():
    """Test that missing required fields return proper error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing 'source' field
        response = await client.post(
            "/v1/events",
            json={"type": "test.event", "payload": {"foo": "bar"}}
        )
        assert response.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_structured_error_response():
    """Test that errors return structured responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            json={"source": "test", "type": "test.event", "payload": "not-a-dict"}
        )
        # Should get 400 for invalid payload type
        assert response.status_code in [400, 422]
        data = response.json()
        # Structured error response should have error field
        assert "error" in data or "detail" in data


@pytest.mark.asyncio
async def test_valid_event_processing():
    """Test that valid events are processed successfully."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            json={
                "source": "test-service",
                "type": "user.created",
                "payload": {"user_id": "123", "email": "test@example.com"}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "id" in data
        assert "correlation_id" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test that health endpoint works."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
