"""
Planner's real-estate intent categories (lead_qualification,
property_matching, site_visit, customer_relations - added Phase 10A,
Step 9; real_estate_sales added Phase 10C). Deterministic, zero-LLM-
cost keyword classification only.

Phase 10C: all five now route to their real, registered employees
(lead_qualifier, property_matcher, real_estate_sales, site_visit,
customer_relations - app/agents/orchestrator.py), superseding every
earlier "route to manager, no employee yet" placeholder. Note
real_estate_sales is deliberately a DIFFERENT employee from the legacy
generic "sales" (see app/agents/real_estate_sales_agent.py's module
docstring) - the "sales" intent/employee is completely unaffected.

Confirms the pre-existing intents (receptionist/sales/support/etc.) are
completely unaffected.

Run: python3 -m pytest tests/test_planner_realestate_intents.py -q   (from backend/)
"""

from app.agents.planner import Planner


class TestRealEstateIntentsRouteToTheirRealEmployee:
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

    def test_real_estate_sales_intent_routes_to_real_estate_sales_not_legacy_sales(self):
        plan = Planner().plan("What's the next best action for this lead?")
        assert plan.intent == "real_estate_sales"
        assert plan.employees == ["real_estate_sales"]

    def test_customer_relations_intent_routes_to_customer_relations(self):
        plan = Planner().plan("Let's follow up with this customer next week.")
        assert plan.intent == "customer_relations"
        assert plan.employees == ["customer_relations"]

    def test_site_visit_intent_routes_to_site_visit_alongside_receptionist(self):
        # "site visit" (this list) and "schedule" (receptionist's list)
        # both match - multi-intent is expected and correct; receptionist
        # has the higher priority (lower number) so it wins as primary,
        # but site_visit's real employee must also be present.
        plan = Planner().plan("Can we schedule a site visit for this property?")
        assert plan.intent == "receptionist"
        assert set(plan.employees) == {"receptionist", "site_visit"}

    def test_no_message_ever_routes_a_real_estate_intent_to_manager(self):
        for message in [
            "site visit please", "follow up with the customer", "nurture the lead over time",
            "qualify the lead", "recommend a property that matches this client's needs",
            "next best action for this lead",
        ]:
            plan = Planner().plan(message)
            assert "manager" not in plan.employees


class TestRealEstateSalesNeverCollidesWithLegacySales:
    def test_a_plain_pricing_question_still_routes_only_to_legacy_sales(self):
        plan = Planner().plan("What's the price for this?")
        assert plan.intent == "sales"
        assert plan.employees == ["sales"]
        assert "real_estate_sales" not in plan.employees

    def test_next_best_action_wording_never_also_matches_legacy_sales(self):
        plan = Planner().plan("Is this lead stalled? What's the next best action?")
        assert "sales" not in plan.employees
        assert plan.employees == ["real_estate_sales"]


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
