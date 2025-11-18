"""API routes for rules management."""
from fastapi import APIRouter, HTTPException
from ..rules.models import Rule
from ..rules.persistence import rule_persistence
from ..rules.engine import RulesEngine
from pydantic import BaseModel

router = APIRouter(prefix="/v1/rules", tags=["rules"])

# Global rules engine instance
# TODO: Move to dependency injection
rules_engine = RulesEngine()


class RuleListResponse(BaseModel):
    """Response for listing rules."""
    total: int
    rules: list[Rule]


@router.post("", response_model=Rule, status_code=201)
async def create_rule(rule: Rule):
    """Create a new routing rule."""
    # Check if rule already exists
    existing = await rule_persistence.get(rule.id)
    if existing:
        raise HTTPException(400, detail=f"Rule with ID {rule.id} already exists")

    # Save and add to engine
    saved = await rule_persistence.save(rule)
    rules_engine.add_rule(saved)

    return saved


@router.get("", response_model=RuleListResponse)
async def list_rules():
    """List all routing rules."""
    rules = await rule_persistence.list_all()
    return RuleListResponse(total=len(rules), rules=rules)


@router.get("/{rule_id}", response_model=Rule)
async def get_rule(rule_id: str):
    """Get a specific rule by ID."""
    rule = await rule_persistence.get(rule_id)
    if not rule:
        raise HTTPException(404, detail=f"Rule {rule_id} not found")
    return rule


@router.put("/{rule_id}", response_model=Rule)
async def update_rule(rule_id: str, rule: Rule):
    """Update an existing rule."""
    if rule_id != rule.id:
        raise HTTPException(400, detail="Rule ID in path must match rule ID in body")

    existing = await rule_persistence.get(rule_id)
    if not existing:
        raise HTTPException(404, detail=f"Rule {rule_id} not found")

    # Save and update engine
    saved = await rule_persistence.save(rule)
    rules_engine.remove_rule(rule_id)
    rules_engine.add_rule(saved)

    return saved


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: str):
    """Delete a rule."""
    deleted = await rule_persistence.delete(rule_id)
    if not deleted:
        raise HTTPException(404, detail=f"Rule {rule_id} not found")

    rules_engine.remove_rule(rule_id)
    return None
