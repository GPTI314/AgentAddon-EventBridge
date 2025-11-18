"""Metrics collector for tracking system performance."""
import time
from typing import Dict, List
from collections import defaultdict
import structlog

log = structlog.get_logger()


class MetricsCollector:
    """
    Collects and aggregates metrics for the event bridge.

    Tracks:
    - Event ingestion counts
    - Publish latency
    - Error counts
    - WebSocket connections
    """

    def __init__(self):
        """Initialize metrics collector."""
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._start_time = time.time()

    def increment(self, metric: str, value: int = 1, labels: Dict[str, str] | None = None):
        """
        Increment a counter metric.

        Args:
            metric: Metric name
            value: Amount to increment by
            labels: Optional labels for the metric
        """
        key = self._make_key(metric, labels)
        self._counters[key] += value
        log.debug("metric.increment", metric=metric, value=value, labels=labels)

    def gauge(self, metric: str, value: float, labels: Dict[str, str] | None = None):
        """
        Set a gauge metric.

        Args:
            metric: Metric name
            value: Gauge value
            labels: Optional labels for the metric
        """
        key = self._make_key(metric, labels)
        self._gauges[key] = value
        log.debug("metric.gauge", metric=metric, value=value, labels=labels)

    def histogram(self, metric: str, value: float, labels: Dict[str, str] | None = None):
        """
        Record a histogram value.

        Args:
            metric: Metric name
            value: Value to record
            labels: Optional labels for the metric
        """
        key = self._make_key(metric, labels)
        self._histograms[key].append(value)
        log.debug("metric.histogram", metric=metric, value=value, labels=labels)

    def record_latency(self, metric: str, start_time: float, labels: Dict[str, str] | None = None):
        """
        Record latency in milliseconds.

        Args:
            metric: Metric name
            start_time: Start timestamp
            labels: Optional labels for the metric
        """
        latency_ms = (time.time() - start_time) * 1000
        self.histogram(metric, latency_ms, labels)

    def get_metrics(self) -> Dict:
        """
        Get all collected metrics.

        Returns:
            Dictionary of all metrics
        """
        uptime = time.time() - self._start_time

        # Calculate histogram stats
        histogram_stats = {}
        for key, values in self._histograms.items():
            if values:
                histogram_stats[key] = {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }

        return {
            "uptime_seconds": uptime,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": histogram_stats,
        }

    def reset(self):
        """Reset all metrics (useful for testing)."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._start_time = time.time()
        log.info("metrics.reset")

    @staticmethod
    def _make_key(metric: str, labels: Dict[str, str] | None) -> str:
        """
        Create a metric key with labels.

        Args:
            metric: Metric name
            labels: Optional labels

        Returns:
            Formatted metric key
        """
        if not labels:
            return metric

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{metric}{{{label_str}}}"


# Global metrics collector instance
collector = MetricsCollector()


# Common metric names
EVENTS_INGESTED_TOTAL = "events_ingested_total"
PUBLISH_LATENCY_MS = "publish_latency_ms"
EVENTS_FILTERED_TOTAL = "events_filtered_total"
WEBSOCKET_CONNECTIONS = "websocket_connections"
HTTP_REQUESTS_TOTAL = "http_requests_total"
HTTP_REQUEST_DURATION_MS = "http_request_duration_ms"
ERRORS_TOTAL = "errors_total"
