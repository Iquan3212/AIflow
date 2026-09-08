"""
Deterministic condition evaluation - no LLM involved anywhere in this
module (Step 7: "Do NOT make the LLM the condition evaluator for basic
structured conditions"). A condition is `{"field": "lead.status", "op":
"eq", "value": "new"}`; evaluate_conditions() ANDs every condition in a
workflow's `conditions` list together - a workflow with zero conditions
always passes (fires unconditionally on its trigger).

Conditions only ever read from the structured trigger_data dict built by
triggers.py (see config.py's TRIGGER_FIELDS) - never from raw user text,
never from a retrieved Knowledge Base document, so there is nothing here
for a prompt-injection attempt to reach (Step 21).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.workflows.config import (
    CONDITION_OPERATORS,
    OPERATOR_CONTAINS,
    OPERATOR_EQ,
    OPERATOR_IS_NOT_SET,
    OPERATOR_IS_SET,
    OPERATOR_NEQ,
)


class ConditionError(Exception):
    """A condition dict itself is malformed (unknown field/operator) - a
    real validation failure, raised at workflow save time (see
    service.py) so a broken condition can never be silently ignored at
    run time."""


@dataclass
class ConditionResult:
    field: str
    op: str
    expected: object
    actual: object
    passed: bool


def _resolve_field(trigger_data: dict, field: str):
    """`field` is a dotted path like "lead.status" - trigger_data is
    always a plain, one-level-nested dict of dicts (see triggers.py), so
    a simple two-part split is enough; never a general-purpose expression
    evaluator."""
    parts = field.split(".", 1)
    if len(parts) != 2:
        return None
    root, key = parts
    return (trigger_data.get(root) or {}).get(key)


def validate_condition(condition: dict, valid_fields: set[str]) -> None:
    field = condition.get("field")
    op = condition.get("op")
    if field not in valid_fields:
        raise ConditionError(f"Unknown condition field for this trigger: {field!r}")
    if op not in CONDITION_OPERATORS:
        raise ConditionError(f"Unknown condition operator: {op!r}")
    if op in (OPERATOR_EQ, OPERATOR_NEQ, OPERATOR_CONTAINS) and "value" not in condition:
        raise ConditionError(f"Operator {op!r} requires a 'value'")


def evaluate_condition(condition: dict, trigger_data: dict) -> ConditionResult:
    field = condition["field"]
    op = condition["op"]
    expected = condition.get("value")
    actual = _resolve_field(trigger_data, field)

    if op == OPERATOR_EQ:
        passed = actual == expected
    elif op == OPERATOR_NEQ:
        passed = actual != expected
    elif op == OPERATOR_IS_SET:
        passed = actual is not None and actual != ""
    elif op == OPERATOR_IS_NOT_SET:
        passed = actual is None or actual == ""
    elif op == OPERATOR_CONTAINS:
        passed = isinstance(actual, str) and isinstance(expected, str) and expected.lower() in actual.lower()
    else:
        raise ConditionError(f"Unknown condition operator: {op!r}")

    return ConditionResult(field=field, op=op, expected=expected, actual=actual, passed=passed)


def evaluate_conditions(conditions: list[dict], trigger_data: dict) -> tuple[bool, list[ConditionResult]]:
    """Returns (all_passed, per-condition results) - the results list is
    what gets persisted as part of the WorkflowRun's audit trail (Step 14:
    "condition results"), so a run's "why did/didn't this fire" is always
    explainable after the fact, not just a bare pass/fail."""
    results = [evaluate_condition(c, trigger_data) for c in conditions]
    return all(r.passed for r in results), results
