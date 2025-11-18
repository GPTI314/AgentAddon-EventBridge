"""
In-memory token store with automatic expiry and cleanup
"""

import threading
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging

from .token_models import Token

logger = logging.getLogger(__name__)


class InMemoryTokenStore:
    """
    Thread-safe in-memory store for ephemeral tokens with automatic cleanup
    """

    def __init__(self, cleanup_interval_seconds: int = 60):
        """
        Initialize token store

        Args:
            cleanup_interval_seconds: Interval for automatic cleanup of expired tokens
        """
        self._store: Dict[str, Token] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_timer: Optional[threading.Timer] = None
        self._shutdown = False

        # Start automatic cleanup
        self._schedule_cleanup()

    def store(self, token: Token) -> None:
        """
        Store a token

        Args:
            token: Token to store
        """
        with self._lock:
            self._store[token.token_id] = token
            logger.debug(f"Stored token {token.token_id}, expires at {token.expires_at}")

    def get(self, token_id: str) -> Optional[Token]:
        """
        Retrieve a token by ID

        Args:
            token_id: Token identifier

        Returns:
            Token if found and not expired, None otherwise
        """
        with self._lock:
            token = self._store.get(token_id)

            if token is None:
                logger.debug(f"Token {token_id} not found")
                return None

            if token.is_expired:
                logger.debug(f"Token {token_id} has expired")
                # Remove expired token
                del self._store[token_id]
                return None

            return token

    def remove(self, token_id: str) -> bool:
        """
        Remove a token from the store

        Args:
            token_id: Token identifier

        Returns:
            True if token was removed, False if not found
        """
        with self._lock:
            if token_id in self._store:
                del self._store[token_id]
                logger.debug(f"Removed token {token_id}")
                return True
            return False

    def cleanup_expired(self) -> int:
        """
        Remove all expired tokens from the store

        Returns:
            Number of tokens removed
        """
        with self._lock:
            now = datetime.utcnow()
            expired_ids = [
                token_id for token_id, token in self._store.items()
                if token.expires_at <= now
            ]

            for token_id in expired_ids:
                del self._store[token_id]

            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} expired tokens")

            return len(expired_ids)

    def count(self) -> int:
        """
        Get count of active (non-expired) tokens

        Returns:
            Number of active tokens
        """
        with self._lock:
            # Clean up expired tokens first
            self.cleanup_expired()
            return len(self._store)

    def count_all(self) -> int:
        """
        Get count of all tokens (including expired)

        Returns:
            Total number of tokens in store
        """
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        """Clear all tokens from the store"""
        with self._lock:
            self._store.clear()
            logger.info("Cleared all tokens from store")

    def _schedule_cleanup(self) -> None:
        """Schedule the next automatic cleanup"""
        if self._shutdown:
            return

        self._cleanup_timer = threading.Timer(
            self._cleanup_interval,
            self._run_cleanup
        )
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _run_cleanup(self) -> None:
        """Run cleanup and schedule next one"""
        try:
            self.cleanup_expired()
        except Exception as e:
            logger.error(f"Error during token cleanup: {e}")
        finally:
            if not self._shutdown:
                self._schedule_cleanup()

    def shutdown(self) -> None:
        """Shutdown the store and cancel cleanup timer"""
        self._shutdown = True
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        logger.info("Token store shutdown")

    def __len__(self) -> int:
        """Get count of active tokens"""
        return self.count()

    def __contains__(self, token_id: str) -> bool:
        """Check if token exists and is not expired"""
        return self.get(token_id) is not None
