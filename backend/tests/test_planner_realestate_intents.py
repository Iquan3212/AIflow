"""
Planner's real-estate intent categories (lead_qualification,
property_matching, site_visit, customer_relations - added Phase 10A,
Step 9). Deterministic, zero-LLM-cost keyword classification only.

Phase 10B: lead_qualification and property_matching now route to real,
registered employees (lead_qualifier/property_matcher -
app/agents/orchestrator.py), superseding the Phase 10A placeholder that
routed every new intent to "manager". site_visit and customer_relations
still have no employee (that's 10C/10D) and still route to "manager",
exactly like the existing "gmail" intent does for the same reason.

Confirms the pre-existing intents (receptionist/sales/support/etc.) are
completely unaffected.

Run: python3 -m pytest tests/test_planner_realestate_intents.py -q   (from backend/)
"""

from app.agents.planner import Planner


class TestBuiltRealEstateIntentsRouteToTheirRealEmployee:
    def test_property_matching_intent_routes_to_property_matcher(self):
        # Deliberately avoids "buy"/"buyer" - "buy" is already a "sales"
        # keyword and is a substring of "buyer", so a message containing
        # it would legitimately multi-match both intents.
        plan = Planner().plan("Can you recommend a property that matches this client's needs?")
        assert plan.intent == "property_matching"
        assert plan.employees == ["property_matcher"]

    def test_lead_qualification_intent_routes_to_lead_qualifier(self):
        plan = Planner().plan("Please qualify the lead before we proceed.")
        assert plan.intent == "lead_qualification"
        assert plan.employees == ["lead_qualifier"]


class TestNotYetBuiltRealEstateIntentsStillRouteToManager:
    def test_site_visit_intent_detected(self):
        # "site visit" (this list) and "schedule" (receptionist's list)
        # both match - multi-intent is expected and correct; receptionist
        # has the higher priority (lower number) so it wins as primary,
        # but "manager" must still be present for the site_visit intent.
        plan = Planner().plan("Can we schedule a site visit for this property?")
        assert plan.intent == "receptionist"
        assert set(plan.employees) == {"receptionist", "manager"}

    def test_customer_relations_intent_detected(self):
        plan = Planner().plan("Let's follow up with this customer next week.")
        assert plan.intent == "customer_relations"
        assert plan.employees == ["manager"]

    def test_no_10c_10d_employee_is_ever_returned(self):
        for message in ["site visit please", "follow up with the customer", "nurture the lead over time"]:
            plan = Planner().plan(message)
            for name in ("site_visit", "customer_relations"):
                assert name not in plan.employees


class TestExistingIntentsUnaffected:
    def test_plain_appointment_message_still_routes_to_receptionist(self):
        plan = Planner().plan("I'd like to book an appointment for tomorrow.")
        assert plan.intent == "receptionist"
        assert plan.employees == ["receptionist"]

    def test_plain_sales_message_still_routes_to_sales(self):
        plan = Planner().plan("What's the price for this?")
        assert plan.intent == "sales"
        assert plan.employees == ["sales"]

    def test_general_message_with_no_keywords_still_falls_back_to_manager(self):
        plan = Planner().plan("Hello there, how are you?")
        assert plan.intent == "general"
        assert plan.employees == ["manager"]
