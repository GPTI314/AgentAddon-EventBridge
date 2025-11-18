"""
Comprehensive tests for Token Service

Tests cover:
- Token issuance with various TTLs
- Token validation (valid and invalid cases)
- Token expiry mechanisms
- In-memory store operations
- Cleanup of expired tokens
- API endpoints
"""

import pytest
import time
from datetime import datetime, timedelta

from app.services.crypto import (
    TokenService,
    TokenScope,
    TokenIssuanceRequest,
    InMemoryTokenStore,
    Token
)
from app.services.crypto.token_service import TokenIssuanceError


class TestTokenIssuance:
    """Test token issuance functionality"""

    def test_issue_token_basic(self):
        """Test basic token issuance"""
        service = TokenService()
        scope = TokenScope(resource="api/users", actions=["read", "write"])

        response = service.issue_token(scope=scope, ttl_seconds=300)

        assert response.token_id is not None
        assert len(response.token_id) > 0
        assert response.scope == scope
        assert response.ttl_seconds == 300
        assert response.expires_at > datetime.utcnow()

    def test_issue_token_with_metadata(self):
        """Test token issuance with metadata"""
        service = TokenService()
        scope = TokenScope(resource="api/data", actions=["read"])
        metadata = {"user_id": "123", "session": "abc"}

        response = service.issue_token(scope=scope, ttl_seconds=60, metadata=metadata)

        # Verify token was stored with metadata
        token = service.get_token_info(response.token_id)
        assert token is not None
        assert token.metadata == metadata

    def test_issue_token_custom_ttl(self):
        """Test token issuance with various TTL values"""
        service = TokenService()
        scope = TokenScope(resource="test", actions=["test"])

        ttls = [1, 60, 300, 600, 3600]
        for ttl in ttls:
            response = service.issue_token(scope=scope, ttl_seconds=ttl)
            assert response.ttl_seconds == ttl

    def test_issue_token_invalid_ttl_too_low(self):
        """Test that TTL below 1 second raises error"""
        service = TokenService()
        scope = TokenScope(resource="test", actions=["test"])

        with pytest.raises(TokenIssuanceError, match="at least 1 second"):
            service.issue_token(scope=scope, ttl_seconds=0)

        with pytest.raises(TokenIssuanceError):
            service.issue_token(scope=scope, ttl_seconds=-1)

    def test_issue_token_invalid_ttl_too_high(self):
        """Test that TTL above 3600 seconds raises error"""
        service = TokenService()
        scope = TokenScope(resource="test", actions=["test"])

        with pytest.raises(TokenIssuanceError, match="cannot exceed 3600"):
            service.issue_token(scope=scope, ttl_seconds=3601)

    def test_issue_token_from_request(self):
        """Test token issuance from request object"""
        service = TokenService()
        request = TokenIssuanceRequest(
            scope=TokenScope(resource="api/posts", actions=["create"]),
            ttl_seconds=120,
            metadata={"client": "web"}
        )

        response = service.issue_token_from_request(request)

        assert response.token_id is not None
        assert response.scope.resource == "api/posts"
        assert response.ttl_seconds == 120

    def test_issue_multiple_tokens_unique_ids(self):
        """Test that multiple tokens have unique IDs"""
        service = TokenService()
        scope = TokenScope(resource="test", actions=["test"])

        tokens = [service.issue_token(scope=scope) for _ in range(10)]
        token_ids = [t.token_id for t in tokens]

        # All token IDs should be unique
        assert len(set(token_ids)) == len(token_ids)


class TestTokenValidation:
    """Test token validation functionality"""

    def test_validate_valid_token(self):
        """Test validation of a valid token"""
        service = TokenService()
        scope = TokenScope(resource="api/test", actions=["read"])

        # Issue token
        issued = service.issue_token(scope=scope, ttl_seconds=60)

        # Validate token
        validation = service.validate_token(issued.token_id)

        assert validation.valid is True
        assert validation.token_id == issued.token_id
        assert validation.scope == scope
        assert validation.ttl_remaining > 0
        assert validation.reason is None

    def test_validate_nonexistent_token(self):
        """Test validation of non-existent token"""
        service = TokenService()

        validation = service.validate_token("nonexistent-token-id")

        assert validation.valid is False
        assert validation.reason is not None
        assert "not found" in validation.reason.lower()

    def test_validate_expired_token(self):
        """Test validation of expired token"""
        service = TokenService()
        scope = TokenScope(resource="api/test", actions=["read"])

        # Issue token with 1 second TTL
        issued = service.issue_token(scope=scope, ttl_seconds=1)

        # Wait for token to expire
        time.sleep(2)

        # Validate expired token
        validation = service.validate_token(issued.token_id)

        assert validation.valid is False
        assert "expired" in validation.reason.lower() or "not found" in validation.reason.lower()

    def test_token_ttl_remaining(self):
        """Test TTL remaining calculation"""
        service = TokenService()
        scope = TokenScope(resource="api/test", actions=["read"])

        # Issue token with 10 second TTL
        issued = service.issue_token(scope=scope, ttl_seconds=10)

        # Immediately validate
        validation = service.validate_token(issued.token_id)

        assert validation.valid is True
        assert validation.ttl_remaining is not None
        # Should have close to 10 seconds remaining (allow some margin)
        assert 9.5 <= validation.ttl_remaining <= 10.0

        # Wait 2 seconds
        time.sleep(2)

        # Validate again
        validation2 = service.validate_token(issued.token_id)
        assert validation2.valid is True
        # Should have ~8 seconds remaining
        assert 7.5 <= validation2.ttl_remaining <= 8.5


class TestTokenRevocation:
    """Test token revocation functionality"""

    def test_revoke_valid_token(self):
        """Test revoking a valid token"""
        service = TokenService()
        scope = TokenScope(resource="api/test", actions=["read"])

        # Issue token
        issued = service.issue_token(scope=scope, ttl_seconds=300)

        # Verify token is valid
        validation = service.validate_token(issued.token_id)
        assert validation.valid is True

        # Revoke token
        revoked = service.revoke_token(issued.token_id)
        assert revoked is True

        # Verify token is no longer valid
        validation2 = service.validate_token(issued.token_id)
        assert validation2.valid is False

    def test_revoke_nonexistent_token(self):
        """Test revoking a non-existent token"""
        service = TokenService()

        revoked = service.revoke_token("nonexistent-token")
        assert revoked is False

    def test_revoke_already_revoked_token(self):
        """Test revoking an already revoked token"""
        service = TokenService()
        scope = TokenScope(resource="api/test", actions=["read"])

        # Issue and revoke token
        issued = service.issue_token(scope=scope, ttl_seconds=300)
        service.revoke_token(issued.token_id)

        # Try to revoke again
        revoked_again = service.revoke_token(issued.token_id)
        assert revoked_again is False


class TestInMemoryTokenStore:
    """Test in-memory token store"""

    def test_store_and_retrieve_token(self):
        """Test storing and retrieving a token"""
        store = InMemoryTokenStore()
        token = Token(
            token_id="test-token-123",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() + timedelta(seconds=60)
        )

        store.store(token)
        retrieved = store.get("test-token-123")

        assert retrieved is not None
        assert retrieved.token_id == "test-token-123"

    def test_get_nonexistent_token(self):
        """Test retrieving non-existent token"""
        store = InMemoryTokenStore()

        retrieved = store.get("nonexistent")
        assert retrieved is None

    def test_get_expired_token(self):
        """Test retrieving expired token returns None"""
        store = InMemoryTokenStore()
        token = Token(
            token_id="expired-token",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() - timedelta(seconds=1)  # Already expired
        )

        store.store(token)
        retrieved = store.get("expired-token")

        # Should return None for expired token and remove it
        assert retrieved is None
        assert "expired-token" not in store

    def test_remove_token(self):
        """Test removing a token"""
        store = InMemoryTokenStore()
        token = Token(
            token_id="test-token",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() + timedelta(seconds=60)
        )

        store.store(token)
        assert store.get("test-token") is not None

        removed = store.remove("test-token")
        assert removed is True
        assert store.get("test-token") is None

    def test_cleanup_expired_tokens(self):
        """Test automatic cleanup of expired tokens"""
        store = InMemoryTokenStore(cleanup_interval_seconds=999999)  # Disable auto cleanup

        # Add valid token
        valid_token = Token(
            token_id="valid",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() + timedelta(seconds=60)
        )
        store.store(valid_token)

        # Add expired tokens
        for i in range(5):
            expired = Token(
                token_id=f"expired-{i}",
                scope=TokenScope(resource="test", actions=["read"]),
                expires_at=datetime.utcnow() - timedelta(seconds=1)
            )
            store.store(expired)

        # Should have 6 tokens total (1 valid + 5 expired)
        assert store.count_all() == 6

        # Run cleanup
        removed = store.cleanup_expired()

        # Should have removed 5 expired tokens
        assert removed == 5
        assert store.count() == 1
        assert store.get("valid") is not None

    def test_count_tokens(self):
        """Test counting tokens"""
        store = InMemoryTokenStore(cleanup_interval_seconds=999999)

        assert store.count() == 0

        # Add tokens
        for i in range(3):
            token = Token(
                token_id=f"token-{i}",
                scope=TokenScope(resource="test", actions=["read"]),
                expires_at=datetime.utcnow() + timedelta(seconds=60)
            )
            store.store(token)

        assert store.count() == 3
        assert len(store) == 3

    def test_clear_all_tokens(self):
        """Test clearing all tokens"""
        store = InMemoryTokenStore()

        # Add tokens
        for i in range(5):
            token = Token(
                token_id=f"token-{i}",
                scope=TokenScope(resource="test", actions=["read"]),
                expires_at=datetime.utcnow() + timedelta(seconds=60)
            )
            store.store(token)

        assert store.count() == 5

        store.clear()
        assert store.count() == 0

    def test_contains_operator(self):
        """Test 'in' operator for token store"""
        store = InMemoryTokenStore()
        token = Token(
            token_id="test-token",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() + timedelta(seconds=60)
        )

        store.store(token)

        assert "test-token" in store
        assert "nonexistent" not in store

    def test_shutdown(self):
        """Test store shutdown"""
        store = InMemoryTokenStore()
        store.shutdown()
        # Should not raise error


class TestTokenServiceStatistics:
    """Test token service statistics and utility methods"""

    def test_get_active_token_count(self):
        """Test getting count of active tokens"""
        service = TokenService()
        scope = TokenScope(resource="test", actions=["read"])

        assert service.get_active_token_count() == 0

        # Issue tokens
        for _ in range(3):
            service.issue_token(scope=scope, ttl_seconds=60)

        assert service.get_active_token_count() == 3

    def test_cleanup_expired_tokens(self):
        """Test manual cleanup of expired tokens"""
        service = TokenService()
        scope = TokenScope(resource="test", actions=["read"])

        # Issue short-lived tokens
        for _ in range(3):
            service.issue_token(scope=scope, ttl_seconds=1)

        # Wait for expiry
        time.sleep(2)

        # Manual cleanup
        removed = service.cleanup_expired_tokens()
        assert removed == 3

    def test_clear_all_tokens(self):
        """Test clearing all tokens"""
        service = TokenService()
        scope = TokenScope(resource="test", actions=["read"])

        # Issue tokens
        for _ in range(5):
            service.issue_token(scope=scope, ttl_seconds=300)

        assert service.get_active_token_count() == 5

        service.clear_all_tokens()
        assert service.get_active_token_count() == 0

    def test_get_token_info(self):
        """Test getting token information"""
        service = TokenService()
        scope = TokenScope(resource="api/test", actions=["read", "write"])

        issued = service.issue_token(scope=scope, ttl_seconds=120)

        info = service.get_token_info(issued.token_id)
        assert info is not None
        assert info.token_id == issued.token_id
        assert info.scope.resource == "api/test"
        assert info.scope.actions == ["read", "write"]


class TestTokenModels:
    """Test token model classes"""

    def test_token_is_expired_property(self):
        """Test token is_expired property"""
        # Valid token
        token = Token(
            token_id="test",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() + timedelta(seconds=60)
        )
        assert token.is_expired is False

        # Expired token
        expired_token = Token(
            token_id="test",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() - timedelta(seconds=1)
        )
        assert expired_token.is_expired is True

    def test_token_ttl_remaining_property(self):
        """Test token ttl_remaining property"""
        token = Token(
            token_id="test",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() + timedelta(seconds=60)
        )

        # Should have close to 60 seconds remaining
        assert 59.5 <= token.ttl_remaining <= 60.0

        # Expired token should have 0 TTL
        expired_token = Token(
            token_id="test",
            scope=TokenScope(resource="test", actions=["read"]),
            expires_at=datetime.utcnow() - timedelta(seconds=1)
        )
        assert expired_token.ttl_remaining == 0.0

    def test_token_to_dict(self):
        """Test token to_dict method"""
        token = Token(
            token_id="test-123",
            scope=TokenScope(
                resource="api/users",
                actions=["read"],
                metadata={"region": "us-west"}
            ),
            expires_at=datetime.utcnow() + timedelta(seconds=60),
            metadata={"user": "alice"}
        )

        token_dict = token.to_dict()

        assert token_dict["token_id"] == "test-123"
        assert token_dict["scope"]["resource"] == "api/users"
        assert token_dict["scope"]["actions"] == ["read"]
        assert token_dict["metadata"]["user"] == "alice"
        assert "created_at" in token_dict
        assert "expires_at" in token_dict
        assert "is_expired" in token_dict
        assert "ttl_remaining" in token_dict

    def test_token_scope_model(self):
        """Test TokenScope model"""
        scope = TokenScope(
            resource="api/data",
            actions=["read", "write", "delete"],
            metadata={"owner": "admin"}
        )

        assert scope.resource == "api/data"
        assert scope.actions == ["read", "write", "delete"]
        assert scope.metadata["owner"] == "admin"

    def test_token_issuance_request_validation(self):
        """Test TokenIssuanceRequest validation"""
        # Valid request
        request = TokenIssuanceRequest(
            scope=TokenScope(resource="test", actions=["read"]),
            ttl_seconds=300
        )
        assert request.ttl_seconds == 300

        # Test default TTL
        request_default = TokenIssuanceRequest(
            scope=TokenScope(resource="test", actions=["read"])
        )
        assert request_default.ttl_seconds == 300  # Default

        # Test TTL validation
        with pytest.raises(ValueError):
            TokenIssuanceRequest(
                scope=TokenScope(resource="test", actions=["read"]),
                ttl_seconds=0
            )

        with pytest.raises(ValueError):
            TokenIssuanceRequest(
                scope=TokenScope(resource="test", actions=["read"]),
                ttl_seconds=5000
            )


class TestConcurrency:
    """Test thread-safety of token store"""

    def test_concurrent_token_operations(self):
        """Test concurrent token storage and retrieval"""
        import threading

        store = InMemoryTokenStore()
        errors = []

        def store_tokens():
            try:
                for i in range(10):
                    token = Token(
                        token_id=f"token-{threading.current_thread().name}-{i}",
                        scope=TokenScope(resource="test", actions=["read"]),
                        expires_at=datetime.utcnow() + timedelta(seconds=60)
                    )
                    store.store(token)
            except Exception as e:
                errors.append(e)

        # Run multiple threads
        threads = [threading.Thread(target=store_tokens) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0

        # Should have 50 tokens (5 threads * 10 tokens each)
        assert store.count() == 50
