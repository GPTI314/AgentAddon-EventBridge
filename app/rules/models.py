"""Rule definition models."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Any
from enum import Enum


class RuleAction(str, Enum):
    """Supported rule actions."""
    TAG = "tag"
    FILTER = "filter"
    TRANSFORM = "transform"


class RuleCondition(BaseModel):
    """Condition for matching events."""
    field: str = Field(..., description="Field to match (source, type, or payload.key)")
    operator: Literal["equals", "contains", "starts_with", "regex"] = "equals"
    value: str = Field(..., description="Value to match against")


class Rule(BaseModel):
    """Event routing rule definition."""
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    enabled: bool = Field(default=True, description="Whether rule is active")
    priority: int = Field(default=100, description="Rule priority (lower = higher priority)")

    # Matching conditions
    conditions: list[RuleCondition] = Field(
        default_factory=list,
        description="Conditions that must all match (AND logic)"
    )

    # Actions
    action: RuleAction = Field(..., description="Action to perform when rule matches")
    action_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the action"
    )
