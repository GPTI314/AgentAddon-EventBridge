"""
API endpoint tests for token management
"""

import pytest
import time
from fastapi.testclient import TestClient

from app.main import app
from app.api.token_router import get_token_service


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_tokens():
    """Clear all tokens before each test"""
    service = get_token_service()
    service.clear_all_tokens()
    yield
    service.clear_all_tokens()


class TestTokenIssuanceAPI:
    """Test token issuance API endpoints"""

    def test_issue_token_success(self, client):
        """Test successful token issuance"""
        response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/users",
                    "actions": ["read", "write"],
                    "metadata": {}
                },
                "ttl_seconds": 300,
                "metadata": {"client": "test"}
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert "token_id" in data
        assert len(data["token_id"]) > 0
        assert data["scope"]["resource"] == "api/users"
        assert data["scope"]["actions"] == ["read", "write"]
        assert data["ttl_seconds"] == 300
        assert "expires_at" in data

    def test_issue_token_minimal_request(self, client):
        """Test token issuance with minimal request"""
        response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/test",
                    "actions": ["read"]
                }
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["ttl_seconds"] == 300  # Default TTL

    def test_issue_token_custom_ttl(self, client):
        """Test token issuance with custom TTL"""
        ttls = [1, 60, 300, 600, 3600]

        for ttl in ttls:
            response = client.post(
                "/tokens/issue",
                json={
                    "scope": {
                        "resource": "api/test",
                        "actions": ["read"]
                    },
                    "ttl_seconds": ttl
                }
            )

            assert response.status_code == 201
            assert response.json()["ttl_seconds"] == ttl

    def test_issue_token_invalid_ttl_too_low(self, client):
        """Test token issuance with TTL too low"""
        response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/test",
                    "actions": ["read"]
                },
                "ttl_seconds": 0
            }
        )

        assert response.status_code == 422  # Validation error

    def test_issue_token_invalid_ttl_too_high(self, client):
        """Test token issuance with TTL too high"""
        response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/test",
                    "actions": ["read"]
                },
                "ttl_seconds": 5000
            }
        )

        assert response.status_code == 422  # Validation error

    def test_issue_token_missing_scope(self, client):
        """Test token issuance without scope"""
        response = client.post(
            "/tokens/issue",
            json={
                "ttl_seconds": 300
            }
        )

        assert response.status_code == 422  # Validation error


class TestTokenValidationAPI:
    """Test token validation API endpoints"""

    def test_validate_valid_token(self, client):
        """Test validation of valid token"""
        # Issue token
        issue_response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/test",
                    "actions": ["read"]
                },
                "ttl_seconds": 60
            }
        )
        token_id = issue_response.json()["token_id"]

        # Validate token
        validate_response = client.post(
            "/tokens/validate",
            json={"token_id": token_id}
        )

        assert validate_response.status_code == 200
        data = validate_response.json()

        assert data["valid"] is True
        assert data["token_id"] == token_id
        assert data["scope"]["resource"] == "api/test"
        assert data["ttl_remaining"] > 0

    def test_validate_nonexistent_token(self, client):
        """Test validation of non-existent token"""
        response = client.post(
            "/tokens/validate",
            json={"token_id": "nonexistent-token-id"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert data["reason"] is not None

    def test_validate_expired_token(self, client):
        """Test validation of expired token"""
        # Issue token with 1 second TTL
        issue_response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/test",
                    "actions": ["read"]
                },
                "ttl_seconds": 1
            }
        )
        token_id = issue_response.json()["token_id"]

        # Wait for expiry
        time.sleep(2)

        # Validate expired token
        validate_response = client.post(
            "/tokens/validate",
            json={"token_id": token_id}
        )

        assert validate_response.status_code == 200
        data = validate_response.json()

        assert data["valid"] is False


class TestTokenRevocationAPI:
    """Test token revocation API endpoints"""

    def test_revoke_valid_token(self, client):
        """Test revoking a valid token"""
        # Issue token
        issue_response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/test",
                    "actions": ["read"]
                },
                "ttl_seconds": 300
            }
        )
        token_id = issue_response.json()["token_id"]

        # Revoke token
        revoke_response = client.delete(f"/tokens/{token_id}")

        assert revoke_response.status_code == 204

        # Verify token is invalid
        validate_response = client.post(
            "/tokens/validate",
            json={"token_id": token_id}
        )

        assert validate_response.json()["valid"] is False

    def test_revoke_nonexistent_token(self, client):
        """Test revoking non-existent token"""
        response = client.delete("/tokens/nonexistent-token")

        assert response.status_code == 404

    def test_revoke_already_revoked_token(self, client):
        """Test revoking an already revoked token"""
        # Issue token
        issue_response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/test",
                    "actions": ["read"]
                },
                "ttl_seconds": 300
            }
        )
        token_id = issue_response.json()["token_id"]

        # Revoke token
        client.delete(f"/tokens/{token_id}")

        # Try to revoke again
        revoke_again_response = client.delete(f"/tokens/{token_id}")

        assert revoke_again_response.status_code == 404


class TestTokenStatisticsAPI:
    """Test token statistics API endpoints"""

    def test_get_stats_no_tokens(self, client):
        """Test getting stats with no active tokens"""
        response = client.get("/tokens/stats")

        assert response.status_code == 200
        data = response.json()

        assert "active_tokens" in data
        assert data["active_tokens"] == 0

    def test_get_stats_with_tokens(self, client):
        """Test getting stats with active tokens"""
        # Issue 3 tokens
        for _ in range(3):
            client.post(
                "/tokens/issue",
                json={
                    "scope": {
                        "resource": "api/test",
                        "actions": ["read"]
                    },
                    "ttl_seconds": 300
                }
            )

        response = client.get("/tokens/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["active_tokens"] == 3

    def test_cleanup_endpoint(self, client):
        """Test cleanup endpoint"""
        # Issue short-lived tokens
        for _ in range(3):
            client.post(
                "/tokens/issue",
                json={
                    "scope": {
                        "resource": "api/test",
                        "actions": ["read"]
                    },
                    "ttl_seconds": 1
                }
            )

        # Wait for expiry
        time.sleep(2)

        # Trigger cleanup
        response = client.post("/tokens/cleanup")

        assert response.status_code == 200
        data = response.json()

        assert "removed_tokens" in data
        assert data["removed_tokens"] == 3


class TestTokenWorkflow:
    """Test complete token workflows"""

    def test_complete_token_lifecycle(self, client):
        """Test complete token lifecycle: issue, validate, revoke"""
        # 1. Issue token
        issue_response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/users",
                    "actions": ["read", "write", "delete"],
                    "metadata": {"region": "us-west"}
                },
                "ttl_seconds": 600,
                "metadata": {"user_id": "123"}
            }
        )

        assert issue_response.status_code == 201
        token_id = issue_response.json()["token_id"]

        # 2. Validate token (should be valid)
        validate_response = client.post(
            "/tokens/validate",
            json={"token_id": token_id}
        )

        assert validate_response.status_code == 200
        assert validate_response.json()["valid"] is True

        # 3. Check stats
        stats_response = client.get("/tokens/stats")
        assert stats_response.json()["active_tokens"] == 1

        # 4. Revoke token
        revoke_response = client.delete(f"/tokens/{token_id}")
        assert revoke_response.status_code == 204

        # 5. Validate token again (should be invalid)
        validate_again = client.post(
            "/tokens/validate",
            json={"token_id": token_id}
        )
        assert validate_again.json()["valid"] is False

        # 6. Check stats (should be 0)
        stats_final = client.get("/tokens/stats")
        assert stats_final.json()["active_tokens"] == 0

    def test_multiple_tokens_independent(self, client):
        """Test that multiple tokens are independent"""
        # Issue two tokens
        token1_response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/resource1",
                    "actions": ["read"]
                },
                "ttl_seconds": 300
            }
        )
        token1_id = token1_response.json()["token_id"]

        token2_response = client.post(
            "/tokens/issue",
            json={
                "scope": {
                    "resource": "api/resource2",
                    "actions": ["write"]
                },
                "ttl_seconds": 300
            }
        )
        token2_id = token2_response.json()["token_id"]

        # Both should be valid
        assert client.post("/tokens/validate", json={"token_id": token1_id}).json()["valid"]
        assert client.post("/tokens/validate", json={"token_id": token2_id}).json()["valid"]

        # Revoke token1
        client.delete(f"/tokens/{token1_id}")

        # Token1 should be invalid, token2 should still be valid
        assert not client.post("/tokens/validate", json={"token_id": token1_id}).json()["valid"]
        assert client.post("/tokens/validate", json={"token_id": token2_id}).json()["valid"]
