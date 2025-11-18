"""WebSocket event streaming with rate limiting and keepalive."""
import asyncio
import time
import structlog
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
from ..event_models import StoredEvent
from ..services.event_bus import bus
import orjson

log = structlog.get_logger()


class EventStreamManager:
    """
    Manages WebSocket connections for event streaming.

    Features:
    - Broadcasts events to all connected clients
    - Rate limiting per client
    - Ping/pong keepalive
    - Automatic connection cleanup
    """

    def __init__(self):
        """Initialize stream manager."""
        self._connections: Set[WebSocket] = set()
        self._last_event_ts = time.time()

    async def connect(self, websocket: WebSocket):
        """
        Add a new WebSocket connection.

        Args:
            websocket: WebSocket connection to add
        """
        await websocket.accept()
        self._connections.add(websocket)
        log.info("websocket.connected", total_connections=len(self._connections))

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection.

        Args:
            websocket: WebSocket connection to remove
        """
        self._connections.discard(websocket)
        log.info("websocket.disconnected", total_connections=len(self._connections))

    async def broadcast_event(self, event: StoredEvent):
        """
        Broadcast an event to all connected clients.

        Args:
            event: Event to broadcast
        """
        if not self._connections:
            return

        # Serialize event
        message = orjson.dumps({
            "type": "event",
            "data": event.model_dump()
        })

        # Send to all connections
        disconnected = set()
        for connection in self._connections:
            try:
                await connection.send_bytes(message)
            except Exception as e:
                log.warning("websocket.send_failed", error=str(e))
                disconnected.add(connection)

        # Cleanup disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def send_ping(self, websocket: WebSocket):
        """
        Send ping message to keep connection alive.

        Args:
            websocket: WebSocket connection
        """
        try:
            await websocket.send_json({"type": "ping", "ts": time.time()})
        except Exception as e:
            log.warning("websocket.ping_failed", error=str(e))

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self._connections)


# Global stream manager instance
stream_manager = EventStreamManager()


class RateLimiter:
    """Simple rate limiter for WebSocket messages."""

    def __init__(self, max_messages: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_messages: Maximum messages allowed in window
            window_seconds: Time window in seconds
        """
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self._message_times: list[float] = []

    def check_limit(self) -> bool:
        """
        Check if rate limit is exceeded.

        Returns:
            True if within limit, False if exceeded
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Remove old messages
        self._message_times = [t for t in self._message_times if t > cutoff]

        # Check limit
        if len(self._message_times) >= self.max_messages:
            return False

        # Record this message
        self._message_times.append(now)
        return True

    def remaining(self) -> int:
        """Get number of remaining messages in current window."""
        now = time.time()
        cutoff = now - self.window_seconds
        recent = len([t for t in self._message_times if t > cutoff])
        return max(0, self.max_messages - recent)


async def handle_websocket_stream(
    websocket: WebSocket,
    ping_interval: int = 30,
    rate_limit_messages: int = 100,
    rate_limit_window: int = 60
):
    """
    Handle WebSocket connection for event streaming.

    Args:
        websocket: WebSocket connection
        ping_interval: Seconds between ping messages (keepalive)
        rate_limit_messages: Max messages per window
        rate_limit_window: Rate limit window in seconds
    """
    rate_limiter = RateLimiter(rate_limit_messages, rate_limit_window)

    await stream_manager.connect(websocket)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "message": "Connected to EventBridge stream",
            "rate_limit": {
                "max_messages": rate_limit_messages,
                "window_seconds": rate_limit_window
            }
        })

        last_ping = time.time()

        while True:
            # Send periodic ping for keepalive
            if time.time() - last_ping > ping_interval:
                await stream_manager.send_ping(websocket)
                last_ping = time.time()

            try:
                # Wait for client messages (e.g., pong responses)
                # Timeout to allow periodic ping checks
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=1.0
                )

                # Check rate limit
                if not rate_limiter.check_limit():
                    await websocket.send_json({
                        "type": "error",
                        "message": "Rate limit exceeded",
                        "retry_after": rate_limit_window
                    })
                    continue

                # Handle client messages
                if message == "pong":
                    log.debug("websocket.pong_received")
                elif message == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # No message received, continue loop for ping check
                continue

    except WebSocketDisconnect:
        log.info("websocket.client_disconnected")
    except Exception as e:
        log.error("websocket.error", error=str(e), exc_info=True)
    finally:
        stream_manager.disconnect(websocket)
