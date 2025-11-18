"""
API routes for EventBridge service.

Provides endpoints for:
- Publishing events
- Listing recent events
"""
from fastapi import APIRouter, HTTPException
from .schemas import PublishRequest, PublishResponse, EventListResponse
from ..services.event_bus import bus
from ..logging import get_logger

router = APIRouter(prefix="/v1")
logger = get_logger()


@router.post("/events", response_model=PublishResponse)
async def publish_event(req: PublishRequest):
    """
    Publish an event to the event bus.

    Args:
        req: Event publication request with type, source, and payload

    Returns:
        PublishResponse with event ID and acceptance status

    Raises:
        HTTPException: If payload is invalid
    """
    if not isinstance(req.payload, dict):
        logger.warning(
            "event_publish_invalid_payload",
            event_type=req.type,
            payload_type=type(req.payload).__name__,
        )
        raise HTTPException(400, detail="Invalid payload - must be a dictionary")

    # Publish event
    stored = bus.publish(req.to_inbound())

    logger.info(
        "event_published",
        event_id=stored.id,
        event_type=stored.type,
        source=stored.source,
    )

    return PublishResponse(id=stored.id, status="accepted")


@router.get("/events", response_model=EventListResponse)
async def list_events(limit: int = 25):
    """
    List recent events from the event bus.

    Args:
        limit: Maximum number of events to return (default: 25)

    Returns:
        EventListResponse with total count and event list
    """
    logger.debug("listing_events", limit=limit)

    events = [e for e in bus.list_recent(limit=limit)]

    logger.debug("events_listed", count=len(events))

    return EventListResponse(total=len(events), events=events)
