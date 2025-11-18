from pydantic import BaseModel, Field
from typing import Any, Dict, List
from ..event_models import InboundEvent, StoredEvent

class PublishRequest(BaseModel):
    source: str
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None

    def to_inbound(self) -> InboundEvent:
        return InboundEvent(**self.model_dump())

class PublishResponse(BaseModel):
    id: str
    status: str

class EventListResponse(BaseModel):
    total: int
    events: List[StoredEvent]
