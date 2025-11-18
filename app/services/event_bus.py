"""Event bus service with pluggable backend adapters."""
from ..event_models import InboundEvent, StoredEvent
from ..adapters.base import BusAdapter
from ..adapters.memory import InMemoryAdapter
from ..adapters.redis_stream import RedisStreamAdapter
from ..config import get_settings
from ..metrics.collector import collector, EVENTS_INGESTED_TOTAL, PUBLISH_LATENCY_MS
from typing import Iterable
import structlog
import time

log = structlog.get_logger()
settings = get_settings()


class EventBus:
    """
    Event bus service that delegates to a pluggable backend adapter.

    The adapter is selected based on the BUS_ADAPTER configuration setting.
    """

    def __init__(self, adapter: BusAdapter | None = None):
        """
        Initialize event bus with optional adapter.

        Args:
            adapter: Backend adapter to use (defaults to configured adapter)
        """
        if adapter is None:
            adapter = _create_default_adapter()
        self._adapter = adapter

    async def publish(self, evt: InboundEvent) -> StoredEvent:
        """Publish an event through the configured adapter."""
        start_time = time.time()

        stored = await self._adapter.publish(evt)

        # Record metrics
        collector.increment(EVENTS_INGESTED_TOTAL, labels={"source": evt.source, "type": evt.type})
        collector.record_latency(PUBLISH_LATENCY_MS, start_time)

        return stored

    async def list_recent(self, limit: int = 50) -> Iterable[StoredEvent]:
        """List recent events through the configured adapter."""
        return await self._adapter.list_recent(limit)

    async def health_check(self) -> bool:
        """Check backend adapter health."""
        return await self._adapter.health_check()


def _create_default_adapter() -> BusAdapter:
    """
    Create the default adapter based on configuration.

    Returns:
        BusAdapter instance based on BUS_ADAPTER setting
    """
    if settings.BUS_ADAPTER == "redis":
        if not settings.REDIS_URL:
            log.warning(
                "adapter.fallback",
                requested="redis",
                actual="memory",
                reason="REDIS_URL not configured"
            )
            return InMemoryAdapter()

        log.info("adapter.selected", type="redis", url=str(settings.REDIS_URL))
        return RedisStreamAdapter()
    else:
        log.info("adapter.selected", type="memory")
        return InMemoryAdapter()


# Global event bus instance
bus = EventBus()
