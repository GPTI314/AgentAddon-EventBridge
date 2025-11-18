"""Tests for event bus adapters."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.adapters.memory import InMemoryAdapter
from app.adapters.redis_stream import RedisStreamAdapter
from app.event_models import InboundEvent
import orjson


@pytest.mark.asyncio
async def test_memory_adapter_publish():
    """Test in-memory adapter can publish events."""
    adapter = InMemoryAdapter()
    event = InboundEvent(
        source="test",
        type="test.event",
        payload={"key": "value"}
    )

    stored = await adapter.publish(event)

    assert stored.id is not None
    assert stored.ts is not None
    assert stored.source == "test"
    assert stored.type == "test.event"
    assert stored.payload == {"key": "value"}


@pytest.mark.asyncio
async def test_memory_adapter_list_recent():
    """Test in-memory adapter can list recent events."""
    adapter = InMemoryAdapter()

    # Publish multiple events
    for i in range(5):
        await adapter.publish(
            InboundEvent(
                source="test",
                type=f"test.event.{i}",
                payload={"index": i}
            )
        )

    # List recent events
    events = await adapter.list_recent(limit=3)
    events_list = list(events)

    assert len(events_list) == 3
    # Should be in reverse order (newest first)
    assert events_list[0].type == "test.event.4"
    assert events_list[1].type == "test.event.3"
    assert events_list[2].type == "test.event.2"


@pytest.mark.asyncio
async def test_memory_adapter_health_check():
    """Test in-memory adapter health check."""
    adapter = InMemoryAdapter()
    assert await adapter.health_check() is True


@pytest.mark.asyncio
async def test_redis_adapter_publish_with_mock():
    """Test Redis adapter publish with mocked Redis."""
    with patch("app.adapters.redis_stream.Redis") as mock_redis_class:
        # Setup mock
        mock_redis = MagicMock()
        mock_redis_class.from_url.return_value = mock_redis
        mock_redis.xadd.return_value = b"1234567890-0"

        adapter = RedisStreamAdapter(redis_url="redis://localhost:6379")
        event = InboundEvent(
            source="test",
            type="test.event",
            payload={"key": "value"}
        )

        stored = await adapter.publish(event)

        # Verify Redis xadd was called
        assert mock_redis.xadd.called
        call_args = mock_redis.xadd.call_args

        # Check stream key
        assert call_args[0][0] == "eventbridge:events"

        # Check event data was serialized
        event_data = call_args[0][1]["data"]
        parsed = orjson.loads(event_data)
        assert parsed["source"] == "test"
        assert parsed["type"] == "test.event"


@pytest.mark.asyncio
async def test_redis_adapter_list_recent_with_mock():
    """Test Redis adapter list recent with mocked Redis."""
    with patch("app.adapters.redis_stream.Redis") as mock_redis_class:
        # Setup mock
        mock_redis = MagicMock()
        mock_redis_class.from_url.return_value = mock_redis

        # Mock XREVRANGE response
        event1 = {
            "id": "evt-1",
            "source": "test",
            "type": "test.event.1",
            "payload": {"index": 1},
            "ts": 1234567890.0,
            "correlation_id": None
        }
        event2 = {
            "id": "evt-2",
            "source": "test",
            "type": "test.event.2",
            "payload": {"index": 2},
            "ts": 1234567891.0,
            "correlation_id": None
        }

        mock_redis.xrevrange.return_value = [
            (b"1234567891-0", {b"data": orjson.dumps(event2)}),
            (b"1234567890-0", {b"data": orjson.dumps(event1)}),
        ]

        adapter = RedisStreamAdapter(redis_url="redis://localhost:6379")
        events = await adapter.list_recent(limit=2)
        events_list = list(events)

        assert len(events_list) == 2
        assert events_list[0].type == "test.event.2"
        assert events_list[1].type == "test.event.1"

        # Verify xrevrange was called with correct params
        mock_redis.xrevrange.assert_called_once()


@pytest.mark.asyncio
async def test_redis_adapter_health_check_success():
    """Test Redis adapter health check when Redis is available."""
    with patch("app.adapters.redis_stream.Redis") as mock_redis_class:
        mock_redis = MagicMock()
        mock_redis_class.from_url.return_value = mock_redis
        mock_redis.ping.return_value = True

        adapter = RedisStreamAdapter(redis_url="redis://localhost:6379")
        health = await adapter.health_check()

        assert health is True
        mock_redis.ping.assert_called_once()


@pytest.mark.asyncio
async def test_redis_adapter_health_check_failure():
    """Test Redis adapter health check when Redis is unavailable."""
    with patch("app.adapters.redis_stream.Redis") as mock_redis_class:
        mock_redis = MagicMock()
        mock_redis_class.from_url.return_value = mock_redis
        mock_redis.ping.side_effect = Exception("Connection refused")

        adapter = RedisStreamAdapter(redis_url="redis://localhost:6379")
        health = await adapter.health_check()

        assert health is False


@pytest.mark.asyncio
async def test_adapter_selection_memory():
    """Test that memory adapter is selected by default."""
    from app.services.event_bus import EventBus
    from app.adapters.memory import InMemoryAdapter

    bus = EventBus()
    assert isinstance(bus._adapter, InMemoryAdapter)


@pytest.mark.asyncio
async def test_event_bus_with_custom_adapter():
    """Test event bus can use custom adapter."""
    from app.services.event_bus import EventBus

    custom_adapter = InMemoryAdapter()
    bus = EventBus(adapter=custom_adapter)

    event = InboundEvent(source="test", type="test.event", payload={})
    stored = await bus.publish(event)

    assert stored.id is not None

    # Verify it's using the custom adapter
    events = await bus.list_recent()
    assert len(list(events)) == 1
