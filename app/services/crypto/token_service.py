"""
TokenService for ephemeral token issuance and validation
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .crypto_service import CryptoService
from .token_store import InMemoryTokenStore
from .token_models import (
    Token,
    TokenScope,
    TokenIssuanceRequest,
    TokenIssuanceResponse,
    TokenValidationResponse
)

logger = logging.getLogger(__name__)


class TokenServiceError(Exception):
    """Base exception for token service errors"""
    pass


class TokenIssuanceError(TokenServiceError):
    """Raised when token issuance fails"""
    pass


class TokenValidationError(TokenServiceError):
    """Raised when token validation fails"""
    pass


class TokenService:
    """
    Service for managing ephemeral tokens

    Provides:
    - Token issuance with configurable TTL
    - Token validation with expiry checking
    - Automatic cleanup of expired tokens
    """

    def __init__(
        self,
        crypto_service: Optional[CryptoService] = None,
        token_store: Optional[InMemoryTokenStore] = None,
        cleanup_interval: int = 60
    ):
        """
        Initialize TokenService

        Args:
            crypto_service: CryptoService instance for token ID generation
            token_store: Token store instance (creates new if not provided)
            cleanup_interval: Cleanup interval in seconds for expired tokens
        """
        self._crypto = crypto_service or CryptoService()
        self._store = token_store or InMemoryTokenStore(cleanup_interval_seconds=cleanup_interval)

    def issue_token(
        self,
        scope: TokenScope,
        ttl_seconds: int = 300,
        metadata: Optional[dict] = None
    ) -> TokenIssuanceResponse:
        """
        Issue a new ephemeral token

        Args:
            scope: Token scope defining permissions
            ttl_seconds: Time-to-live in seconds (default: 300, max: 3600)
            metadata: Optional metadata to attach to token

        Returns:
            TokenIssuanceResponse with token details

        Raises:
            TokenIssuanceError: If token issuance fails
        """
        try:
            # Validate TTL
            if ttl_seconds < 1:
                raise ValueError("TTL must be at least 1 second")
            if ttl_seconds > 3600:
                raise ValueError("TTL cannot exceed 3600 seconds")

            # Generate secure token ID
            token_id = self._crypto.generate_secret_urlsafe(32)

            # Calculate expiration
            created_at = datetime.utcnow()
            expires_at = created_at + timedelta(seconds=ttl_seconds)

            # Create token
            token = Token(
                token_id=token_id,
                scope=scope,
                created_at=created_at,
                expires_at=expires_at,
                metadata=metadata or {}
            )

            # Store token
            self._store.store(token)

            logger.info(
                f"Issued token {token_id[:8]}... for resource '{scope.resource}' "
                f"with TTL {ttl_seconds}s"
            )

            return TokenIssuanceResponse(
                token_id=token_id,
                scope=scope,
                expires_at=expires_at,
                ttl_seconds=ttl_seconds
            )

        except ValueError as e:
            raise TokenIssuanceError(f"Invalid token parameters: {e}")
        except Exception as e:
            logger.error(f"Failed to issue token: {e}")
            raise TokenIssuanceError(f"Token issuance failed: {e}")

    def issue_token_from_request(
        self,
        request: TokenIssuanceRequest
    ) -> TokenIssuanceResponse:
        """
        Issue token from a TokenIssuanceRequest

        Args:
            request: Token issuance request

        Returns:
            TokenIssuanceResponse
        """
        return self.issue_token(
            scope=request.scope,
            ttl_seconds=request.ttl_seconds,
            metadata=request.metadata
        )

    def validate_token(self, token_id: str) -> TokenValidationResponse:
        """
        Validate a token

        Args:
            token_id: Token identifier to validate

        Returns:
            TokenValidationResponse with validation result
        """
        try:
            token = self._store.get(token_id)

            if token is None:
                logger.debug(f"Token validation failed: {token_id[:8]}... not found or expired")
                return TokenValidationResponse(
                    valid=False,
                    token_id=token_id,
                    reason="Token not found or has expired"
                )

            # Token exists and is not expired (get() already checks expiry)
            logger.debug(f"Token {token_id[:8]}... validated successfully")
            return TokenValidationResponse(
                valid=True,
                token_id=token.token_id,
                scope=token.scope,
                expires_at=token.expires_at,
                ttl_remaining=token.ttl_remaining
            )

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return TokenValidationResponse(
                valid=False,
                token_id=token_id,
                reason=f"Validation error: {e}"
            )

    def revoke_token(self, token_id: str) -> bool:
        """
        Revoke a token (remove from store)

        Args:
            token_id: Token identifier to revoke

        Returns:
            True if token was revoked, False if not found
        """
        revoked = self._store.remove(token_id)
        if revoked:
            logger.info(f"Revoked token {token_id[:8]}...")
        else:
            logger.debug(f"Token {token_id[:8]}... not found for revocation")
        return revoked

    def get_token_info(self, token_id: str) -> Optional[Token]:
        """
        Get token information

        Args:
            token_id: Token identifier

        Returns:
            Token if found and valid, None otherwise
        """
        return self._store.get(token_id)

    def cleanup_expired_tokens(self) -> int:
        """
        Manually trigger cleanup of expired tokens

        Returns:
            Number of tokens removed
        """
        count = self._store.cleanup_expired()
        logger.info(f"Manual cleanup removed {count} expired tokens")
        return count

    def get_active_token_count(self) -> int:
        """
        Get count of active (non-expired) tokens

        Returns:
            Number of active tokens
        """
        return self._store.count()

    def clear_all_tokens(self) -> None:
        """Clear all tokens from the store"""
        self._store.clear()
        logger.warning("Cleared all tokens from store")

    def shutdown(self) -> None:
        """Shutdown the token service"""
        self._store.shutdown()
        logger.info("Token service shutdown")
