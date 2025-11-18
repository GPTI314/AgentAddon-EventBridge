"""Tests for metrics and telemetry."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.metrics.collector import MetricsCollector, collector
import time


@pytest.mark.asyncio
async def test_metrics_endpoint_exists():
    """Test that /metrics endpoint is accessible."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data


@pytest.mark.asyncio
async def test_counter_increment():
    """Test counter increment functionality."""
    test_collector = MetricsCollector()

    test_collector.increment("test_counter")
    test_collector.increment("test_counter")
    test_collector.increment("test_counter", value=3)

    metrics = test_collector.get_metrics()
    assert metrics["counters"]["test_counter"] == 5


@pytest.mark.asyncio
async def test_counter_with_labels():
    """Test counter with labels."""
    test_collector = MetricsCollector()

    test_collector.increment("requests", labels={"method": "GET", "path": "/events"})
    test_collector.increment("requests", labels={"method": "POST", "path": "/events"})
    test_collector.increment("requests", labels={"method": "GET", "path": "/events"})

    metrics = test_collector.get_metrics()
    assert metrics["counters"]["requests{method=GET,path=/events}"] == 2
    assert metrics["counters"]["requests{method=POST,path=/events}"] == 1


@pytest.mark.asyncio
async def test_gauge_value():
    """Test gauge metric."""
    test_collector = MetricsCollector()

    test_collector.gauge("temperature", 23.5)
    test_collector.gauge("temperature", 24.0)  # Update value

    metrics = test_collector.get_metrics()
    assert metrics["gauges"]["temperature"] == 24.0


@pytest.mark.asyncio
async def test_histogram_recording():
    """Test histogram value recording."""
    test_collector = MetricsCollector()

    test_collector.histogram("latency", 10.5)
    test_collector.histogram("latency", 20.0)
    test_collector.histogram("latency", 15.5)

    metrics = test_collector.get_metrics()
    stats = metrics["histograms"]["latency"]

    assert stats["count"] == 3
    assert stats["sum"] == 46.0
    assert stats["min"] == 10.5
    assert stats["max"] == 20.0
    assert abs(stats["avg"] - 15.33) < 0.01  # Average with tolerance


@pytest.mark.asyncio
async def test_latency_recording():
    """Test latency recording."""
    test_collector = MetricsCollector()

    start_time = time.time()
    await asyncio.sleep(0.01)  # Sleep 10ms
    test_collector.record_latency("operation_latency", start_time)

    metrics = test_collector.get_metrics()
    stats = metrics["histograms"]["operation_latency"]

    assert stats["count"] == 1
    assert stats["min"] >= 10  # At least 10ms


@pytest.mark.asyncio
async def test_metrics_reset():
    """Test metrics reset functionality."""
    test_collector = MetricsCollector()

    test_collector.increment("counter", value=10)
    test_collector.gauge("gauge", 50.0)
    test_collector.histogram("hist", 100.0)

    test_collector.reset()

    metrics = test_collector.get_metrics()
    assert len(metrics["counters"]) == 0
    assert len(metrics["gauges"]) == 0
    assert len(metrics["histograms"]) == 0


@pytest.mark.asyncio
async def test_event_ingestion_metrics():
    """Test that event ingestion increments metrics."""
    # Reset global collector
    collector.reset()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Publish an event
        await client.post(
            "/v1/events",
            json={"source": "test", "type": "test.event", "payload": {"key": "value"}}
        )

        # Check metrics
        response = await client.get("/metrics")
        data = response.json()

        # Should have ingestion counter
        assert any("events_ingested_total" in k for k in data["counters"].keys())

        # Should have latency histogram
        assert any("publish_latency_ms" in k for k in data["histograms"].keys())


@pytest.mark.asyncio
async def test_uptime_tracking():
    """Test that uptime is tracked."""
    test_collector = MetricsCollector()

    await asyncio.sleep(0.1)  # Wait a bit

    metrics = test_collector.get_metrics()
    assert metrics["uptime_seconds"] >= 0.1


import asyncio
