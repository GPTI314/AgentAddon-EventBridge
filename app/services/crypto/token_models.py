"""
Token models and schemas for ephemeral token management
"""

from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class TokenScope(BaseModel):
    """
    Scope definition for token permissions
    """
    resource: str = Field(..., description="Resource identifier")
    actions: list[str] = Field(default_factory=list, description="Allowed actions")
    metadata: dict = Field(default_factory=dict, description="Additional scope metadata")


class TokenIssuanceRequest(BaseModel):
    """
    Request to issue a new ephemeral token
    """
    scope: TokenScope
    ttl_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Time-to-live in seconds (1s to 1h)"
    )
    metadata: dict = Field(default_factory=dict, description="Optional metadata")

    @field_validator('ttl_seconds')
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        if v < 1:
            raise ValueError("TTL must be at least 1 second")
        if v > 3600:
            raise ValueError("TTL cannot exceed 3600 seconds (1 hour)")
        return v


class Token(BaseModel):
    """
    Ephemeral token representation
    """
    token_id: str = Field(..., description="Unique token identifier")
    scope: TokenScope
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    metadata: dict = Field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired"""
        return datetime.utcnow() >= self.expires_at

    @property
    def ttl_remaining(self) -> float:
        """Get remaining time-to-live in seconds"""
        if self.is_expired:
            return 0.0
        delta = self.expires_at - datetime.utcnow()
        return delta.total_seconds()

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "token_id": self.token_id,
            "scope": self.scope.model_dump(),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "metadata": self.metadata,
            "is_expired": self.is_expired,
            "ttl_remaining": self.ttl_remaining
        }


class TokenIssuanceResponse(BaseModel):
    """
    Response from token issuance
    """
    token_id: str
    scope: TokenScope
    expires_at: datetime
    ttl_seconds: int
    message: str = "Token issued successfully"


class TokenValidationRequest(BaseModel):
    """
    Request to validate a token
    """
    token_id: str = Field(..., min_length=1)


class TokenValidationResponse(BaseModel):
    """
    Response from token validation
    """
    valid: bool
    token_id: Optional[str] = None
    scope: Optional[TokenScope] = None
    expires_at: Optional[datetime] = None
    ttl_remaining: Optional[float] = None
    reason: Optional[str] = None
