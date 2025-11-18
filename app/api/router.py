from fastapi import APIRouter, HTTPException
from .schemas import PublishRequest, PublishResponse, EventListResponse
from ..services.event_bus import bus

router = APIRouter(prefix="/v1")

@router.post("/events", response_model=PublishResponse)
async def publish_event(req: PublishRequest):
    if isinstance(req.payload, dict):
        stored = bus.publish(req.to_inbound())
        return PublishResponse(id=stored.id, status="accepted")
    raise HTTPException(400, detail="Invalid payload")

@router.get("/events", response_model=EventListResponse)
async def list_events(limit: int = 25):
    events = [e for e in bus.list_recent(limit=limit)]
    return EventListResponse(total=len(events), events=events)
