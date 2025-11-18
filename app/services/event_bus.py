from ..event_models import InboundEvent, StoredEvent
from typing import Iterable
import structlog

log = structlog.get_logger()

class EventBus:
    def __init__(self):
        self._buffer: list[StoredEvent] = []

    def publish(self, evt: InboundEvent) -> StoredEvent:
        stored = StoredEvent(**evt.model_dump())
        self._buffer.append(stored)
        log.info("event.published", id=stored.id, type=stored.type, source=stored.source)
        return stored

    def list_recent(self, limit: int = 50) -> Iterable[StoredEvent]:
        return list(reversed(self._buffer))[:limit]

bus = EventBus()
