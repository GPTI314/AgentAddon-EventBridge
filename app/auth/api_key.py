"""API key authentication."""
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from typing import Optional
import structlog
from ..config import get_settings

log = structlog.get_logger()
settings = get_settings()

# API key header scheme
api_key_header = APIKeyHeader(name="X-EventBridge-Key", auto_error=False)


class APIKeyRegistry:
    """
    In-memory API key registry.

    Keys are loaded from environment variables at startup.
    In production, this should be replaced with a database-backed
    implementation with key rotation support.
    """

    def __init__(self):
        """Initialize API key registry from environment."""
        self._keys: set[str] = set()
        self._load_keys_from_env()

    def _load_keys_from_env(self):
        """
        Load API keys from environment variables.

        Supports:
        - API_KEYS: Comma-separated list of keys
        - API_KEY_1, API_KEY_2, etc.: Individual keys
        """
        # Load from comma-separated list
        if hasattr(settings, "API_KEYS") and settings.API_KEYS:
            keys = settings.API_KEYS.split(",")
            for key in keys:
                key = key.strip()
                if key:
                    self._keys.add(key)

        log.info("api_keys.loaded", count=len(self._keys))

    def validate(self, key: str) -> bool:
        """
        Validate an API key.

        Args:
            key: API key to validate

        Returns:
            True if key is valid
        """
        return key in self._keys

    def add_key(self, key: str):
        """
        Add an API key to the registry.

        Args:
            key: API key to add
        """
        self._keys.add(key)
        log.info("api_key.added")

    def remove_key(self, key: str) -> bool:
        """
        Remove an API key from the registry.

        Args:
            key: API key to remove

        Returns:
            True if key was removed
        """
        if key in self._keys:
            self._keys.discard(key)
            log.info("api_key.removed")
            return True
        return False

    def count(self) -> int:
        """Get total number of registered keys."""
        return len(self._keys)


# Global registry instance
registry = APIKeyRegistry()


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Dependency to verify API key from request header.

    Args:
        api_key: API key from X-EventBridge-Key header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    # If no keys are configured, skip authentication
    if registry.count() == 0:
        log.debug("auth.skipped", reason="no_keys_configured")
        return "anonymous"

    if not api_key:
        log.warning("auth.failed", reason="missing_key")
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-EventBridge-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    if not registry.validate(api_key):
        log.warning("auth.failed", reason="invalid_key")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    log.debug("auth.success")
    return api_key
