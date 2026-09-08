"""
Regression tests for the real, live-confirmed multi-intent bug:
"Find emails in my inbox containing the word invoice." legitimately routes
to BOTH "finance" (keyword "invoice") and "manager" (keyword "email"/
"inbox") - Planner correctly includes both (see
test_planner_gmail_multi_intent.py). Manager's own gmail_search succeeds
for real, but FinanceAgent - which has no awareness Gmail even exists -
independently generates an honest-for-itself but system-wide-wrong
blanket denial ("I don't have access to your Gmail or any external email
accounts."), which the old _merge_replies() blindly concatenated right
next to Manager's correct answer.

ManagerAgent.delegate() now calls _reconcile_cross_employee_capability_
denials() right before merging, which strips ONLY the denial sentence(s)
from a non-contributing employee's reply when a SIBLING employee in the
same turn genuinely succeeded - Finance is never removed from routing,
and a Finance reply with real, relevant content is never discarded.

Real employee agents / generate_employee_reply() are NOT used here -
employee.respond() is stubbed to return exactly the real, observed reply
shapes, so this is a pure, zero-token test of the merge/reconciliation
logic itself.

Run: python3 -m pytest tests/test_manager_agent_merge_reconciliation.py -q   (from backend/)
"""

from unittest.mock import MagicMock

from app.agents.manager_agent import (
    ManagerAgent,
    _reconcile_cross_employee_capability_denials,
    _strip_capability_denial_sentences,
)


def _build_manager():
    registry = MagicMock()
    memory = MagicMock()
    memory.shared_context.return_value = {"facts": []}
    business = MagicMock()
    business.name = "Biryani House"
    return ManagerAgent(registry=registry, memory=memory, business=business)


class FakePlan:
    def __init__(self, employees):
        self.intent = "finance"
        self.confidence = 0.9
        self.priority = 15
        self.employees = employees
        self.tools = []


class TestSentenceLevelStripping:
    def test_strips_only_the_denial_sentence_keeps_the_rest(self):
        text = "Your invoice total is $50. I don't have access to your Gmail though."
        cleaned = _strip_capability_denial_sentences(text)
        assert "invoice total is $50" in cleaned
        assert "don't have access" not in cleaned.lower()

    def test_pure_denial_becomes_empty(self):
        text = "I'm sorry, but I don't have access to your Gmail or any external email accounts."
        assert _strip_capability_denial_sentences(text) == ""

    def test_no_denial_present_is_untouched(self):
        text = "Your invoice total is $50."
        assert _strip_capability_denial_sentences(text) == text


class TestReconciliationFunctionDirectly:
    def test_denial_from_a_non_contributing_employee_is_stripped_when_a_sibling_succeeded(self):
        employee_results = {
            "finance": {
                "reply": "I'm sorry, but I don't have access to your Gmail or any external email accounts.",
                "tool_result": {"ok": False, "error": "no_lead_details"},
            },
            "manager": {
                "reply": "I found 2 emails matching 'invoice': Invoice #1, Invoice #2.",
                "tool_result": {"ok": True, "results": [{"subject": "Invoice #1"}, {"subject": "Invoice #2"}]},
            },
        }

        _reconcile_cross_employee_capability_denials(employee_results)

        assert employee_results["finance"]["reply"] == ""
        assert employee_results["manager"]["reply"] == "I found 2 emails matching 'invoice': Invoice #1, Invoice #2."

    def test_relevant_finance_content_is_preserved_alongside_the_denial(self):
        """Finance is never discarded wholesale - a genuinely relevant
        sentence survives even when a spurious denial sentence next to it
        does not."""
        employee_results = {
            "finance": {
                "reply": "Your invoice total for this month is $120. I don't have access to your Gmail though.",
                "tool_result": {"ok": False, "error": "no_lead_details"},
            },
            "manager": {
                "reply": "Here are your invoice emails: Invoice #1.",
                "tool_result": {"ok": True, "results": [{"subject": "Invoice #1"}]},
            },
        }

        _reconcile_cross_employee_capability_denials(employee_results)

        assert "invoice total for this month is $120" in employee_results["finance"]["reply"]
        assert "don't have access" not in employee_results["finance"]["reply"].lower()

    def test_no_sibling_success_leaves_an_honest_denial_alone(self):
        """Nothing to reconcile against - if EVERY employee failed/has no
        result, an "I can't do that" may be a correct, honest answer and
        must not be silently erased."""
        employee_results = {
            "finance": {
                "reply": "I don't have access to your Gmail or any external email accounts.",
                "tool_result": {"ok": False, "error": "no_lead_details"},
            },
            "manager": {
                "reply": "I don't have access to your Gmail right now.",
                "tool_result": {"ok": False, "error": "not_connected"},
            },
        }

        _reconcile_cross_employee_capability_denials(employee_results)

        assert "don't have access" in employee_results["finance"]["reply"].lower()
        assert "don't have access" in employee_results["manager"]["reply"].lower()

    def test_single_employee_is_never_touched(self):
        """len(employee_results) < 2 short-circuits - a lone employee's
        own honest "I can't do that" is left completely alone."""
        employee_results = {
            "finance": {
                "reply": "I don't have access to your Gmail.",
                "tool_result": {"ok": False, "error": "no_lead_details"},
            },
        }

        _reconcile_cross_employee_capability_denials(employee_results)

        assert employee_results["finance"]["reply"] == "I don't have access to your Gmail."

    def test_an_employee_whose_own_tool_succeeded_is_never_stripped_even_if_it_denies_something_else(self):
        """own_succeeded short-circuits per-employee - only a NON-
        contributing employee's denial is ever touched."""
        employee_results = {
            "finance": {
                "reply": "Your quotation is ready. I don't have access to appointment scheduling though.",
                "tool_result": {"ok": True, "draft": "quotation-123"},
            },
            "manager": {
                "reply": "Here's your latest email.",
                "tool_result": {"ok": True, "results": [{"subject": "Latest"}]},
            },
        }

        _reconcile_cross_employee_capability_denials(employee_results)

        assert employee_results["finance"]["reply"] == (
            "Your quotation is ready. I don't have access to appointment scheduling though."
        )


class TestDelegateEndToEndReconciliation:
    """The real bug's exact shape, reproduced through ManagerAgent.delegate()
    itself (employee.respond() stubbed - no real LLM/tool calls) - proves
    the merged final_reply a caller actually receives is fixed, not just
    the internal employee_results dict."""

    def test_the_real_observed_bug_is_fixed_end_to_end(self):
        manager = _build_manager()

        finance_stub = MagicMock()
        finance_stub.respond.return_value = {
            "reply": "I'm sorry, but I don't have access to your Gmail or any external email accounts.",
            "tool_result": {"ok": False, "error": "no_lead_details"},
        }
        manager_stub_for_registry = MagicMock()
        manager_stub_for_registry.respond.return_value = {
            "reply": "I found 11 emails matching 'invoice', including a receipt from Anthropic and an Amazon refund confirmation.",
            "tool_result": {"ok": True, "results": [{"subject": "Your receipt from Anthropic, PBC"}]},
        }

        def get_employee(name):
            return {"finance": finance_stub, "manager": manager_stub_for_registry}.get(name)
        manager.registry.get_employee.side_effect = get_employee

        plan = FakePlan(employees=["finance", "manager"])
        result = manager.delegate(plan, "Find emails in my inbox containing the word invoice.", [])

        assert "don't have access" not in result["final_reply"].lower()
        assert "Anthropic" in result["final_reply"]

    def test_normal_multi_intent_merge_without_any_denial_is_unaffected(self):
        """Sanity check the fix doesn't change ordinary, non-contradictory
        multi-employee merges (e.g. "create a lead and book an
        appointment") - both parts must still appear, labeled."""
        manager = _build_manager()

        sales_stub = MagicMock()
        sales_stub.respond.return_value = {"reply": "Lead created for Rahul.", "tool_result": {"ok": True, "lead_id": "123"}}
        receptionist_stub = MagicMock()
        receptionist_stub.respond.return_value = {"reply": "Appointment booked for 3pm.", "tool_result": {"ok": True}}

        def get_employee(name):
            return {"sales": sales_stub, "receptionist": receptionist_stub}.get(name)
        manager.registry.get_employee.side_effect = get_employee

        plan = FakePlan(employees=["sales", "receptionist"])
        result = manager.delegate(plan, "Create a lead and book an appointment.", [])

        assert "Sales: Lead created for Rahul." in result["final_reply"]
        assert "Receptionist: Appointment booked for 3pm." in result["final_reply"]
