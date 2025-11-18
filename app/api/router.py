from fastapi import APIRouter, HTTPException, Request, Depends
from .schemas import PublishRequest, PublishResponse, EventListResponse
from ..services.event_bus import bus
from ..auth.api_key import verify_api_key
from ..config import get_settings

router = APIRouter(prefix="/v1")
settings = get_settings()


@router.post("/events", response_model=PublishResponse)
async def publish_event(
    req: PublishRequest,
    request: Request,
    api_key: str | None = Depends(verify_api_key) if settings.REQUIRE_AUTH else None
):
    if isinstance(req.payload, dict):
        # Inject correlation_id from middleware if not provided
        if not req.correlation_id and hasattr(request.state, "correlation_id"):
            req.correlation_id = request.state.correlation_id

        stored = await bus.publish(req.to_inbound())
        return PublishResponse(id=stored.id, status="accepted", correlation_id=stored.correlation_id)
    raise HTTPException(400, detail="Invalid payload")


@router.get("/events", response_model=EventListResponse)
async def list_events(
    limit: int = 25,
    api_key: str | None = Depends(verify_api_key) if settings.REQUIRE_AUTH else None
):
    events = [e for e in await bus.list_recent(limit=limit)]
    return EventListResponse(total=len(events), events=events)
