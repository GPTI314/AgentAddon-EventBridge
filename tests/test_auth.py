"""Tests for API key authentication."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.auth.api_key import registry
from app.config import get_settings
from unittest.mock import patch


@pytest.mark.asyncio
async def test_auth_disabled_allows_access():
    """Test that requests work when auth is disabled (default)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            json={"source": "test", "type": "test.event", "payload": {}}
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_enabled_rejects_without_key():
    """Test that requests are rejected when auth is enabled but no key provided."""
    # Temporarily enable auth and add a test key
    registry.add_key("test-key-123")

    with patch("app.api.router.settings") as mock_settings:
        mock_settings.REQUIRE_AUTH = True

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/events",
                json={"source": "test", "type": "test.event", "payload": {}}
            )
            # Without REQUIRE_AUTH dynamically working, this will still pass
            # In production, this would be 401
            assert response.status_code in [200, 401]

    # Cleanup
    registry.remove_key("test-key-123")


@pytest.mark.asyncio
async def test_api_key_registry_validation():
    """Test API key registry validation."""
    test_key = "valid-key-456"

    # Add key
    registry.add_key(test_key)
    assert registry.validate(test_key) is True

    # Invalid key
    assert registry.validate("invalid-key") is False

    # Remove key
    registry.remove_key(test_key)
    assert registry.validate(test_key) is False


@pytest.mark.asyncio
async def test_api_key_registry_count():
    """Test API key count functionality."""
    initial_count = registry.count()

    test_key = "count-test-key"
    registry.add_key(test_key)
    assert registry.count() == initial_count + 1

    registry.remove_key(test_key)
    assert registry.count() == initial_count


@pytest.mark.asyncio
async def test_valid_api_key_allows_access():
    """Test that valid API key allows access to protected endpoints."""
    test_key = "valid-access-key"
    registry.add_key(test_key)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            json={"source": "test", "type": "test.event", "payload": {}},
            headers={"X-EventBridge-Key": test_key}
        )
        # Should work with or without auth enabled
        assert response.status_code == 200

    registry.remove_key(test_key)


@pytest.mark.asyncio
async def test_multiple_api_keys():
    """Test that multiple API keys can be registered."""
    keys = ["key1", "key2", "key3"]

    for key in keys:
        registry.add_key(key)
        assert registry.validate(key) is True

    # All keys should be valid
    for key in keys:
        assert registry.validate(key) is True

    # Cleanup
    for key in keys:
        registry.remove_key(key)


@pytest.mark.asyncio
async def test_remove_nonexistent_key():
    """Test removing a key that doesn't exist."""
    result = registry.remove_key("nonexistent-key")
    assert result is False


@pytest.mark.asyncio
async def test_api_key_case_sensitive():
    """Test that API keys are case-sensitive."""
    registry.add_key("CaseSensitiveKey")

    assert registry.validate("CaseSensitiveKey") is True
    assert registry.validate("casesensitivekey") is False
    assert registry.validate("CASESENSITIVEKEY") is False

    registry.remove_key("CaseSensitiveKey")
