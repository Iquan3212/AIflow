"""
Deterministic condition evaluation - pure functions, zero DB, zero LLM
tokens.

Run: python3 -m pytest tests/test_workflow_conditions.py -q   (from backend/)
"""

import pytest

from app.services.workflows.conditions import (
    ConditionError,
    evaluate_conditions,
    validate_condition,
)

VALID_FIELDS = {"lead.status", "lead.service_interested"}


class TestValidateCondition:
    def test_unknown_field_rejected(self):
        with pytest.raises(ConditionError):
            validate_condition({"field": "lead.nonexistent", "op": "eq", "value": "x"}, VALID_FIELDS)

    def test_unknown_operator_rejected(self):
        with pytest.raises(ConditionError):
            validate_condition({"field": "lead.status", "op": "regex_match", "value": "x"}, VALID_FIELDS)

    def test_eq_without_value_rejected(self):
        with pytest.raises(ConditionError):
            validate_condition({"field": "lead.status", "op": "eq"}, VALID_FIELDS)

    def test_is_set_without_value_is_fine(self):
        validate_condition({"field": "lead.status", "op": "is_set"}, VALID_FIELDS)

    def test_valid_condition_passes(self):
        validate_condition({"field": "lead.status", "op": "eq", "value": "new"}, VALID_FIELDS)


class TestEvaluateCondition:
    def test_eq_true(self):
        passed, results = evaluate_conditions(
            [{"field": "lead.status", "op": "eq", "value": "new"}], {"lead": {"status": "new"}},
        )
        assert passed is True
        assert results[0].passed is True

    def test_eq_false(self):
        passed, _ = evaluate_conditions(
            [{"field": "lead.status", "op": "eq", "value": "new"}], {"lead": {"status": "contacted"}},
        )
        assert passed is False

    def test_neq(self):
        passed, _ = evaluate_conditions(
            [{"field": "lead.status", "op": "neq", "value": "lost"}], {"lead": {"status": "new"}},
        )
        assert passed is True

    def test_is_set_true_and_false(self):
        passed, _ = evaluate_conditions([{"field": "lead.service_interested", "op": "is_set"}], {"lead": {"service_interested": "Haircut"}})
        assert passed is True
        passed, _ = evaluate_conditions([{"field": "lead.service_interested", "op": "is_set"}], {"lead": {"service_interested": None}})
        assert passed is False
        passed, _ = evaluate_conditions([{"field": "lead.service_interested", "op": "is_set"}], {"lead": {}})
        assert passed is False

    def test_is_not_set(self):
        passed, _ = evaluate_conditions([{"field": "lead.service_interested", "op": "is_not_set"}], {"lead": {}})
        assert passed is True

    def test_contains_case_insensitive(self):
        passed, _ = evaluate_conditions(
            [{"field": "lead.service_interested", "op": "contains", "value": "HAIR"}],
            {"lead": {"service_interested": "Hair coloring"}},
        )
        assert passed is True

    def test_multiple_conditions_all_must_pass(self):
        conditions = [
            {"field": "lead.status", "op": "eq", "value": "new"},
            {"field": "lead.service_interested", "op": "is_set"},
        ]
        passed, results = evaluate_conditions(conditions, {"lead": {"status": "new", "service_interested": "Consulting"}})
        assert passed is True
        assert len(results) == 2

        passed, _ = evaluate_conditions(conditions, {"lead": {"status": "new", "service_interested": None}})
        assert passed is False

    def test_no_conditions_always_passes(self):
        passed, results = evaluate_conditions([], {"lead": {"status": "anything"}})
        assert passed is True
        assert results == []

    def test_missing_root_key_resolves_to_none_not_a_crash(self):
        passed, _ = evaluate_conditions([{"field": "lead.status", "op": "eq", "value": "new"}], {})
        assert passed is False
