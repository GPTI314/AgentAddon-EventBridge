"""
Structured logging configuration using structlog.

Standardized log format:
{
    "ts": "2025-11-18T04:30:00.123456Z",
    "level": "info",
    "service": "eventbridge",
    "correlation_id": "uuid-v4",
    "event": "message",
    "module": "app.api.router",
    "function": "publish_event",
    "line": 42,
    ...additional context...
}
"""
import structlog
import logging
from typing import Any


def add_service_name(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Add service name to all log entries."""
    event_dict["service"] = "eventbridge"
    return event_dict


def add_module_info(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Add module, function, and line number to log entries."""
    # Get call site info
    frame = structlog._frames._find_first_app_frame_and_name()[0]
    if frame:
        event_dict["module"] = frame.f_globals.get("__name__", "unknown")
        event_dict["function"] = frame.f_code.co_name
        event_dict["line"] = frame.f_lineno
    return event_dict


def rename_event_key(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Rename 'event' key to match our standard (it's the log message)."""
    # structlog uses 'event' for the message by default, which matches our standard
    return event_dict


def setup_logging(json_output: bool = True, service_name: str = "eventbridge"):
    """
    Configure structured logging with standardized fields.

    Args:
        json_output: If True, output JSON logs. If False, use console format.
        service_name: Name of the service (for multi-service deployments).
    """
    # Shared processors
    shared_processors = [
        # Add contextvars (includes correlation_id from middleware)
        structlog.contextvars.merge_contextvars,
        # Add service name
        add_service_name,
        # Add timestamp as 'ts'
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        # Add log level as 'level'
        structlog.processors.add_log_level,
        # Add module/function/line info
        add_module_info,
        # Add stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exceptions
        structlog.processors.format_exc_info,
    ]

    if json_output:
        # JSON output for production
        processors = shared_processors + [
            # Render as JSON
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console output for development
        processors = shared_processors + [
            # Render for console
            structlog.dev.ConsoleRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )

    # Silence uvicorn's default logging to avoid duplicate logs
    logging.getLogger("uvicorn.error").handlers = []
    logging.getLogger("uvicorn.access").handlers = []


def get_logger():
    """Get a configured structlog logger."""
    return structlog.get_logger()
