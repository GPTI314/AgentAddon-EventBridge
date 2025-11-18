import structlog, logging

def setup_logging(json: bool = True):
    if json:
        processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [structlog.processors.TimeStamper(fmt="iso"), structlog.dev.ConsoleRenderer()]
    structlog.configure(processors=processors)
    logging.getLogger("uvicorn.error").handlers = []
