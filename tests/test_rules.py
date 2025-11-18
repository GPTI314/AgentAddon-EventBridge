"""Tests for routing rules engine."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.rules.engine import RulesEngine
from app.rules.models import Rule, RuleCondition, RuleAction
from app.event_models import StoredEvent
import time


@pytest.mark.asyncio
async def test_rule_matches_source():
    """Test rule matching on event source."""
    engine = RulesEngine()
    rule = Rule(
        id="rule-1",
        name="Match test source",
        conditions=[
            RuleCondition(field="source", operator="equals", value="test-service")
        ],
        action=RuleAction.TAG,
        action_params={"tags": ["matched"]}
    )
    engine.add_rule(rule)

    event = StoredEvent(
        source="test-service",
        type="test.event",
        payload={}
    )

    result = engine.evaluate(event)
    assert "rule-1" in result["matched_rules"]
    assert "matched" in result["tags"]


@pytest.mark.asyncio
async def test_rule_matches_type():
    """Test rule matching on event type."""
    engine = RulesEngine()
    rule = Rule(
        id="rule-2",
        name="Match event type",
        conditions=[
            RuleCondition(field="type", operator="starts_with", value="user.")
        ],
        action=RuleAction.TAG,
        action_params={"tags": ["user-event"]}
    )
    engine.add_rule(rule)

    event = StoredEvent(
        source="api",
        type="user.created",
        payload={}
    )

    result = engine.evaluate(event)
    assert "rule-2" in result["matched_rules"]
    assert "user-event" in result["tags"]


@pytest.mark.asyncio
async def test_rule_matches_payload_field():
    """Test rule matching on payload field."""
    engine = RulesEngine()
    rule = Rule(
        id="rule-3",
        name="Match payload field",
        conditions=[
            RuleCondition(field="payload.priority", operator="equals", value="high")
        ],
        action=RuleAction.TAG,
        action_params={"tags": ["high-priority"]}
    )
    engine.add_rule(rule)

    event = StoredEvent(
        source="api",
        type="task.created",
        payload={"priority": "high", "user_id": "123"}
    )

    result = engine.evaluate(event)
    assert "rule-3" in result["matched_rules"]
    assert "high-priority" in result["tags"]


@pytest.mark.asyncio
async def test_rule_multiple_conditions():
    """Test rule with multiple conditions (AND logic)."""
    engine = RulesEngine()
    rule = Rule(
        id="rule-4",
        name="Multiple conditions",
        conditions=[
            RuleCondition(field="source", operator="equals", value="payment-service"),
            RuleCondition(field="payload.amount", operator="contains", value="100")
        ],
        action=RuleAction.TAG,
        action_params={"tags": ["large-payment"]}
    )
    engine.add_rule(rule)

    # Should match
    event1 = StoredEvent(
        source="payment-service",
        type="payment.received",
        payload={"amount": "1000"}
    )
    result1 = engine.evaluate(event1)
    assert "rule-4" in result1["matched_rules"]

    # Should not match (wrong source)
    event2 = StoredEvent(
        source="other-service",
        type="payment.received",
        payload={"amount": "1000"}
    )
    result2 = engine.evaluate(event2)
    assert "rule-4" not in result2["matched_rules"]


@pytest.mark.asyncio
async def test_rule_filter_action():
    """Test filter action marks event as filtered."""
    engine = RulesEngine()
    rule = Rule(
        id="rule-5",
        name="Filter spam",
        conditions=[
            RuleCondition(field="payload.spam", operator="equals", value="true")
        ],
        action=RuleAction.FILTER,
        action_params={}
    )
    engine.add_rule(rule)

    event = StoredEvent(
        source="api",
        type="message.received",
        payload={"spam": "true"}
    )

    result = engine.evaluate(event)
    assert result["filtered"] is True


@pytest.mark.asyncio
async def test_rule_priority_ordering():
    """Test rules are evaluated in priority order."""
    engine = RulesEngine()

    # Lower priority number = higher priority
    rule1 = Rule(
        id="rule-low",
        name="Low priority",
        priority=200,
        conditions=[],
        action=RuleAction.TAG,
        action_params={"tags": ["low"]}
    )

    rule2 = Rule(
        id="rule-high",
        name="High priority",
        priority=50,
        conditions=[],
        action=RuleAction.TAG,
        action_params={"tags": ["high"]}
    )

    engine.add_rule(rule1)
    engine.add_rule(rule2)

    event = StoredEvent(source="test", type="test", payload={})
    result = engine.evaluate(event)

    # Both should match, high priority first
    assert result["matched_rules"] == ["rule-high", "rule-low"]


@pytest.mark.asyncio
async def test_rule_regex_matching():
    """Test regex operator for pattern matching."""
    engine = RulesEngine()
    rule = Rule(
        id="rule-regex",
        name="Regex match",
        conditions=[
            RuleCondition(
                field="payload.email",
                operator="regex",
                value=r".*@example\.com$"
            )
        ],
        action=RuleAction.TAG,
        action_params={"tags": ["example-user"]}
    )
    engine.add_rule(rule)

    event1 = StoredEvent(
        source="api",
        type="user.registered",
        payload={"email": "user@example.com"}
    )
    result1 = engine.evaluate(event1)
    assert "rule-regex" in result1["matched_rules"]

    event2 = StoredEvent(
        source="api",
        type="user.registered",
        payload={"email": "user@other.com"}
    )
    result2 = engine.evaluate(event2)
    assert "rule-regex" not in result2["matched_rules"]


@pytest.mark.asyncio
async def test_rule_disabled():
    """Test disabled rules are not evaluated."""
    engine = RulesEngine()
    rule = Rule(
        id="rule-disabled",
        name="Disabled rule",
        enabled=False,
        conditions=[],
        action=RuleAction.TAG,
        action_params={"tags": ["should-not-apply"]}
    )
    engine.add_rule(rule)

    event = StoredEvent(source="test", type="test", payload={})
    result = engine.evaluate(event)

    assert "rule-disabled" not in result["matched_rules"]
    assert "should-not-apply" not in result["tags"]


@pytest.mark.asyncio
async def test_rules_api_create_rule():
    """Test creating a rule via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rule_data = {
            "id": "api-rule-1",
            "name": "API Test Rule",
            "enabled": True,
            "priority": 100,
            "conditions": [
                {
                    "field": "source",
                    "operator": "equals",
                    "value": "api-test"
                }
            ],
            "action": "tag",
            "action_params": {"tags": ["api-created"]}
        }

        response = await client.post("/v1/rules", json=rule_data)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "api-rule-1"
        assert data["name"] == "API Test Rule"


@pytest.mark.asyncio
async def test_rules_api_list_rules():
    """Test listing rules via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/rules")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "rules" in data
        assert isinstance(data["rules"], list)


@pytest.mark.asyncio
async def test_rules_api_get_rule():
    """Test getting a specific rule via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a rule first
        rule_data = {
            "id": "get-test-rule",
            "name": "Get Test",
            "conditions": [],
            "action": "tag",
            "action_params": {}
        }
        await client.post("/v1/rules", json=rule_data)

        # Get the rule
        response = await client.get("/v1/rules/get-test-rule")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "get-test-rule"


@pytest.mark.asyncio
async def test_rules_api_delete_rule():
    """Test deleting a rule via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a rule first
        rule_data = {
            "id": "delete-test-rule",
            "name": "Delete Test",
            "conditions": [],
            "action": "tag",
            "action_params": {}
        }
        await client.post("/v1/rules", json=rule_data)

        # Delete the rule
        response = await client.delete("/v1/rules/delete-test-rule")
        assert response.status_code == 204

        # Verify it's gone
        response = await client.get("/v1/rules/delete-test-rule")
        assert response.status_code == 404
