from pydantic import BaseModel, Field
from typing import Any, Dict
import uuid, time

class InboundEvent(BaseModel):
    source: str = Field(..., description="Origin identifier")
    type: str = Field(..., description="Event type discriminator")
    payload: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None

class StoredEvent(InboundEvent):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = Field(default_factory=lambda: time.time())
