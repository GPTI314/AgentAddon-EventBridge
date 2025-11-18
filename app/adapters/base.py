"""Base adapter interface for event bus backends."""
from abc import ABC, abstractmethod
from typing import Iterable
from ..event_models import InboundEvent, StoredEvent


class BusAdapter(ABC):
    """Abstract interface for event bus backend implementations."""

    @abstractmethod
    async def publish(self, evt: InboundEvent) -> StoredEvent:
        """
        Publish an event to the backend.

        Args:
            evt: The inbound event to publish

        Returns:
            The stored event with assigned ID and timestamp
        """
        pass

    @abstractmethod
    async def list_recent(self, limit: int = 50) -> Iterable[StoredEvent]:
        """
        Retrieve recent events from the backend.

        Args:
            limit: Maximum number of events to return

        Returns:
            Iterable of recent stored events
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the backend is healthy and accessible.

        Returns:
            True if backend is healthy, False otherwise
        """
        pass
