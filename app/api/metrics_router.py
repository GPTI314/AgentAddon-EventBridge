"""Metrics API endpoint."""
from fastapi import APIRouter
from ..metrics.collector import collector

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics():
    """
    Get current metrics and telemetry data.

    Returns JSON with:
    - uptime_seconds: Service uptime
    - counters: Counter metrics (events ingested, errors, etc.)
    - gauges: Gauge metrics (current connections, etc.)
    - histograms: Histogram metrics with statistics (latency, etc.)

    Example response:
    ```json
    {
      "uptime_seconds": 123.45,
      "counters": {
        "events_ingested_total": 1000,
        "errors_total": 5
      },
      "gauges": {
        "websocket_connections": 3
      },
      "histograms": {
        "publish_latency_ms": {
          "count": 1000,
          "sum": 5000.0,
          "avg": 5.0,
          "min": 1.0,
          "max": 50.0
        }
      }
    }
    ```
    """
    return collector.get_metrics()
