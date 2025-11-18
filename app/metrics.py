"""
Prometheus metrics for EventBridge service.
"""
from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
import psutil
import os


class Metrics:
    """
    Centralized metrics for EventBridge service.
    """

    def __init__(self, service_name: str = "eventbridge", version: str = "0.1.0", registry=None):
        self.service_name = service_name
        self.version = version
        self.registry = registry or CollectorRegistry()

        # HTTP Metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["service", "method", "path", "status"],
            registry=self.registry,
        )

        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["service", "method", "path"],
            registry=self.registry,
        )

        self.http_requests_active = Gauge(
            "http_requests_active",
            "Number of active HTTP requests",
            ["service"],
            labelnames=["service"],
            registry=self.registry,
        )
        self.http_requests_active.labels(service=service_name).set(0)

        # Application Info
        self.app_info = Info(
            "app",
            "Application information",
            registry=self.registry,
        )
        self.app_info.info({"service": service_name, "version": version})

        self.app_up = Gauge(
            "app_up",
            "Application up status (1=up, 0=down)",
            ["service", "version"],
            registry=self.registry,
        )
        self.app_up.labels(service=service_name, version=version).set(1)

        # Business Metrics - EventBridge specific
        self.events_published_total = Counter(
            "eventbridge_events_published_total",
            "Total events published",
            ["event_type"],
            registry=self.registry,
        )

        self.events_active = Gauge(
            "eventbridge_events_active",
            "Number of active events in the system",
            registry=self.registry,
        )

        self.event_size_bytes = Histogram(
            "eventbridge_event_size_bytes",
            "Event payload size in bytes",
            ["event_type"],
            registry=self.registry,
        )

        # System Metrics
        self._setup_process_metrics()

    def _setup_process_metrics(self):
        """Set up process-level metrics using psutil."""
        process = psutil.Process(os.getpid())

        # CPU
        self.process_cpu_seconds = Counter(
            "process_cpu_seconds_total",
            "Total CPU time consumed by process",
            ["service"],
            registry=self.registry,
        )

        # Memory
        self.process_memory_bytes = Gauge(
            "process_resident_memory_bytes",
            "Resident memory size in bytes",
            ["service"],
            registry=self.registry,
        )

        # File descriptors
        self.process_open_fds = Gauge(
            "process_open_fds",
            "Number of open file descriptors",
            ["service"],
            registry=self.registry,
        )

        # Update system metrics
        self.update_system_metrics()

    def update_system_metrics(self):
        """Update system metrics from psutil."""
        try:
            process = psutil.Process(os.getpid())

            # CPU
            cpu_times = process.cpu_times()
            cpu_total = cpu_times.user + cpu_times.system
            # Note: Counter can't be set, we track the value separately
            # For now, we'll use a Gauge for current CPU usage
            if not hasattr(self, "_last_cpu_total"):
                self._last_cpu_total = 0
            cpu_diff = cpu_total - self._last_cpu_total
            if cpu_diff > 0:
                self.process_cpu_seconds.labels(service=self.service_name).inc(cpu_diff)
            self._last_cpu_total = cpu_total

            # Memory
            memory_info = process.memory_info()
            self.process_memory_bytes.labels(service=self.service_name).set(memory_info.rss)

            # File descriptors
            try:
                num_fds = process.num_fds()
                self.process_open_fds.labels(service=self.service_name).set(num_fds)
            except AttributeError:
                # num_fds() not available on all platforms
                pass

        except Exception:
            # Silently ignore errors in metrics collection
            pass

    def record_event_published(self, event_type: str, size_bytes: int):
        """Record an event publication."""
        self.events_published_total.labels(event_type=event_type).inc()
        self.event_size_bytes.labels(event_type=event_type).observe(size_bytes)

    def set_active_events(self, count: int):
        """Set the number of active events."""
        self.events_active.set(count)
