"""Redis Streams event bus adapter."""
from typing import Iterable
import structlog
import orjson
from redis import Redis
from redis.exceptions import RedisError
from .base import BusAdapter
from ..event_models import InboundEvent, StoredEvent
from ..config import get_settings

log = structlog.get_logger()
settings = get_settings()


class RedisStreamAdapter(BusAdapter):
    """Redis Streams implementation of event bus adapter.

    Events are published to a Redis stream and can be queried
    in reverse chronological order.
    """

    def __init__(self, redis_url: str | None = None):
        """
        Initialize Redis stream adapter.

        Args:
            redis_url: Redis connection URL (defaults to settings.REDIS_URL)
        """
        self.redis_url = redis_url or str(settings.REDIS_URL)
        self._client: Redis | None = None
        self._stream_key = "eventbridge:events"

    def _get_client(self) -> Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = Redis.from_url(
                self.redis_url,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5
            )
        return self._client

    async def publish(self, evt: InboundEvent) -> StoredEvent:
        """
        Publish event to Redis stream.

        Args:
            evt: The inbound event to publish

        Returns:
            The stored event with assigned ID

        Raises:
            RedisError: If unable to publish to Redis
        """
        stored = StoredEvent(**evt.model_dump())

        try:
            client = self._get_client()

            # Serialize event to JSON bytes
            event_data = orjson.dumps(stored.model_dump())

            # Add to Redis stream with event ID as the message ID
            client.xadd(
                self._stream_key,
                {"data": event_data},
                id="*",  # Let Redis auto-generate ID
                maxlen=10000  # Keep max 10k events
            )

            log.info(
                "event.published",
                id=stored.id,
                type=stored.type,
                source=stored.source,
                adapter="redis_stream"
            )
            return stored

        except RedisError as e:
            log.error("redis.publish_failed", error=str(e), event_id=stored.id)
            raise

    async def list_recent(self, limit: int = 50) -> Iterable[StoredEvent]:
        """
        List recent events from Redis stream.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events in reverse chronological order
        """
        try:
            client = self._get_client()

            # Read from stream in reverse order
            # XREVRANGE returns entries newest first
            entries = client.xrevrange(self._stream_key, count=limit)

            events = []
            for entry_id, entry_data in entries:
                if b"data" in entry_data:
                    event_dict = orjson.loads(entry_data[b"data"])
                    events.append(StoredEvent(**event_dict))

            return events

        except RedisError as e:
            log.error("redis.list_failed", error=str(e))
            # Return empty list on error rather than failing
            return []

    async def health_check(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            client = self._get_client()
            return client.ping()
        except Exception as e:
            log.warning("redis.health_check_failed", error=str(e))
            return False

    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None
