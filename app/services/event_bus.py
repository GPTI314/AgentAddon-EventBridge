"""
Event bus service for storing and retrieving events.
"""
from ..event_models import InboundEvent, StoredEvent
from typing import Iterable, Optional
import structlog
import json

log = structlog.get_logger()


class EventBus:
    """
    In-memory event bus for storing and retrieving events.

    Supports metrics recording for published events.
    """

    def __init__(self, metrics=None):
        """
        Initialize event bus.

        Args:
            metrics: Optional Metrics instance for recording metrics
        """
        self._buffer: list[StoredEvent] = []
        self._metrics = metrics

    def publish(self, evt: InboundEvent) -> StoredEvent:
        """
        Publish an event to the bus.

        Args:
            evt: Inbound event to publish

        Returns:
            StoredEvent with ID and timestamp
        """
        stored = StoredEvent(**evt.model_dump())
        self._buffer.append(stored)

        # Calculate event size
        event_size = len(json.dumps(stored.payload))

        # Log event publication
        log.info(
            "event_published",
            event_id=stored.id,
            event_type=stored.type,
            source=stored.source,
            size_bytes=event_size,
        )

        # Record metrics if available
        if self._metrics:
            self._metrics.record_event_published(stored.type, event_size)
            self._metrics.set_active_events(len(self._buffer))

        return stored

    def list_recent(self, limit: int = 50) -> Iterable[StoredEvent]:
        """
        List recent events from the bus.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events (newest first)
        """
        return list(reversed(self._buffer))[:limit]


# Singleton instance (metrics will be set via set_metrics)
bus = EventBus()


def set_metrics(metrics):
    """
    Set metrics instance for the bus.

    Args:
        metrics: Metrics instance
    """
    bus._metrics = metrics
