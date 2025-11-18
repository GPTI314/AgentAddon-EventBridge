"""In-memory event bus adapter."""
from typing import Iterable
import structlog
from .base import BusAdapter
from ..event_models import InboundEvent, StoredEvent

log = structlog.get_logger()


class InMemoryAdapter(BusAdapter):
    """In-memory implementation of event bus adapter."""

    def __init__(self):
        self._buffer: list[StoredEvent] = []

    async def publish(self, evt: InboundEvent) -> StoredEvent:
        """Publish event to in-memory buffer."""
        stored = StoredEvent(**evt.model_dump())
        self._buffer.append(stored)
        log.info(
            "event.published",
            id=stored.id,
            type=stored.type,
            source=stored.source,
            adapter="memory"
        )
        return stored

    async def list_recent(self, limit: int = 50) -> Iterable[StoredEvent]:
        """List recent events from memory buffer."""
        return list(reversed(self._buffer))[:limit]

    async def health_check(self) -> bool:
        """In-memory adapter is always healthy."""
        return True
