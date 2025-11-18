"""Rules engine for event processing."""
import re
import structlog
from typing import Any
from .models import Rule, RuleCondition
from ..event_models import StoredEvent

log = structlog.get_logger()


class RulesEngine:
    """Engine for evaluating and executing routing rules on events."""

    def __init__(self, rules: list[Rule] | None = None):
        """
        Initialize rules engine.

        Args:
            rules: List of rules to evaluate (defaults to empty list)
        """
        self.rules = rules or []
        self._sort_rules()

    def _sort_rules(self):
        """Sort rules by priority (lower number = higher priority)."""
        self.rules.sort(key=lambda r: r.priority)

    def add_rule(self, rule: Rule):
        """Add a rule to the engine."""
        self.rules.append(rule)
        self._sort_rules()
        log.info("rule.added", rule_id=rule.id, rule_name=rule.name)

    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a rule by ID.

        Returns:
            True if rule was removed, False if not found
        """
        initial_count = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rule_id]
        removed = len(self.rules) < initial_count
        if removed:
            log.info("rule.removed", rule_id=rule_id)
        return removed

    def get_rule(self, rule_id: str) -> Rule | None:
        """Get a rule by ID."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def list_rules(self) -> list[Rule]:
        """List all rules."""
        return self.rules.copy()

    def evaluate(self, event: StoredEvent) -> dict[str, Any]:
        """
        Evaluate all rules against an event.

        Args:
            event: The event to evaluate

        Returns:
            Dictionary with evaluation results:
            - matched_rules: List of rule IDs that matched
            - tags: Set of tags to apply
            - filtered: Whether event should be filtered out
            - transformed: Transformed event data (if any)
        """
        result = {
            "matched_rules": [],
            "tags": set(),
            "filtered": False,
            "transformed": None
        }

        for rule in self.rules:
            if not rule.enabled:
                continue

            if self._matches_rule(event, rule):
                result["matched_rules"].append(rule.id)
                log.debug("rule.matched", rule_id=rule.id, event_id=event.id)

                # Execute action
                self._execute_action(event, rule, result)

                # If filtered, stop processing
                if result["filtered"]:
                    break

        return result

    def _matches_rule(self, event: StoredEvent, rule: Rule) -> bool:
        """
        Check if event matches all rule conditions.

        Args:
            event: Event to check
            rule: Rule to evaluate

        Returns:
            True if all conditions match
        """
        if not rule.conditions:
            # No conditions = always match
            return True

        for condition in rule.conditions:
            if not self._matches_condition(event, condition):
                return False

        return True

    def _matches_condition(self, event: StoredEvent, condition: RuleCondition) -> bool:
        """
        Check if event matches a single condition.

        Args:
            event: Event to check
            condition: Condition to evaluate

        Returns:
            True if condition matches
        """
        # Extract field value from event
        field_value = self._get_field_value(event, condition.field)

        if field_value is None:
            return False

        # Convert to string for comparison
        field_str = str(field_value)
        target_str = str(condition.value)

        # Evaluate based on operator
        if condition.operator == "equals":
            return field_str == target_str
        elif condition.operator == "contains":
            return target_str in field_str
        elif condition.operator == "starts_with":
            return field_str.startswith(target_str)
        elif condition.operator == "regex":
            try:
                return re.match(condition.value, field_str) is not None
            except re.error as e:
                log.warning("rule.invalid_regex", error=str(e), pattern=condition.value)
                return False

        return False

    def _get_field_value(self, event: StoredEvent, field: str) -> Any:
        """
        Extract field value from event.

        Supports:
        - source, type, id, ts, correlation_id
        - payload.key for nested payload access

        Args:
            event: Event to extract from
            field: Field path (e.g., "source" or "payload.user_id")

        Returns:
            Field value or None if not found
        """
        if field.startswith("payload."):
            # Extract from payload
            key = field[8:]  # Remove "payload." prefix
            if isinstance(event.payload, dict):
                return event.payload.get(key)
            return None
        else:
            # Direct field access
            return getattr(event, field, None)

    def _execute_action(self, event: StoredEvent, rule: Rule, result: dict):
        """
        Execute rule action and update result.

        Args:
            event: Event being processed
            rule: Rule to execute
            result: Result dictionary to update
        """
        if rule.action == "tag":
            # Add tags from action params
            tags = rule.action_params.get("tags", [])
            if isinstance(tags, list):
                result["tags"].update(tags)
            elif isinstance(tags, str):
                result["tags"].add(tags)

        elif rule.action == "filter":
            # Mark event as filtered
            result["filtered"] = True
            log.info("rule.filtered", rule_id=rule.id, event_id=event.id)

        elif rule.action == "transform":
            # Store transformation parameters
            result["transformed"] = rule.action_params.copy()
