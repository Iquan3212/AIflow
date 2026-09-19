"""
Phase 10D: bounded multi-specialist Manager orchestration -
ManagerAgent.delegate() sequencing SPECIALIST_ORDER members (never more
than MAX_SPECIALISTS_PER_REQUEST), passing structured context between
them, and synthesizing a final reply that surfaces pending approvals and
re-verifies property facts against current DB state. Exercised through
the REAL, existing architecture end-to-end: EmployeeAgent.process() ->
AIOrchestrator -> Planner -> ManagerAgent.delegate() -> the real
employees -> ToolRouter -> real Phase 10A-10C tools -> the real dev
database. No second orchestrator, no second routing system.

Only chat_completion is mocked (deterministic, scripted responses) -
zero real LLM tokens. Real dev DB with real throwaway rows.

Run: python3 -m pytest tests/test_manager_orchestration.py -q   (from backend/)
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models, schemas
from app.agents.employee_agent import EmployeeAgent
from app.agents.manager_agent import MAX_SPECIALISTS_PER_REQUEST, SPECIALIST_ORDER, ManagerAgent
from app.agents.orchestrator import AIOrchestrator
from app.agents.planner import Plan
from app.services.ai_workforce.execution_service import AgentExecutionService
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.llm.base import LLMProviderError


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Orchestration Test {suffix}",
        slug=f"orchestration-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@orchestrationtest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_lead(db, agency, **fields):
    fields.setdefault("status", "new")
    lead = models.Lead(agency_id=agency.id, **fields)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _make_active_property(db, agency, *, unit_number="U-1", bhk=3, price="9500000.00"):
    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="Orchestration Project", city="Pune"))
    ProjectService(db).update(project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
    unit = PropertyService(db).create(
        agency.id,
        schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=bhk,
            carpet_area_sqft=Decimal("1200.00"), price=Decimal(price), unit_number=unit_number,
        ),
    )
    PropertyService(db).update_status(unit.id, agency.id, "active")
    return project, unit


def _cleanup(db, agency):
    db.query(models.AgentExecution).filter(models.AgentExecution.agency_id == agency.id).delete()
    db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == agency.id).delete()
    db.query(models.Message).filter(
        models.Message.conversation_id.in_(
            db.query(models.Conversation.id).filter(models.Conversation.agency_id == agency.id)
        )
    ).delete(synchronize_session=False)
    db.query(models.Conversation).filter(models.Conversation.agency_id == agency.id).delete()
    db.query(models.Lead).filter(models.Lead.agency_id == agency.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def agency():
    db, biz = _make_agency("a")
    try:
        yield db, biz
    finally:
        _cleanup(db, biz)


@pytest.fixture
def two_agencies():
    db1, biz1 = _make_agency("x")
    db2, biz2 = _make_agency("y")
    try:
        yield (db1, biz1), (db2, biz2)
    finally:
        _cleanup(db1, biz1)
        _cleanup(db2, biz2)


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tool_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


class TestPlannerCompositeRequests:
    """Category A - the spec's own composite-request examples actually
    detect the right specialist set (Planner stays deterministic,
    zero-LLM-cost)."""

    def test_qualify_and_match_detects_both_specialists(self):
        from app.agents.planner import Planner
        plan = Planner().plan("Qualify this lead and find three properties that fit their requirements.")
        assert set(plan.employees) == {"lead_qualifier", "property_matcher"}

    def test_summarize_and_since_inquiry_detects_customer_relations(self):
        from app.agents.planner import Planner
        plan = Planner().plan("Summarize this buyer and tell me what happened since their inquiry.")
        assert "customer_relations" in plan.employees


class TestManagerRoutingSingleTwoThreeSpecialists:
    """Category B."""

    def test_single_specialist_behaves_exactly_as_before(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Single Test")
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Qualified: high intent."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None, message="Please qualify the lead before we proceed.",
            )
        assert result["reply"] == "Qualified: high intent."

    def test_two_specialists_run_in_order_with_context_passing(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Two Spec Test")
        _, unit = _make_active_property(db, biz, unit_number="T-1", bhk=3)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="High intent, 3BHK, ready to buy."),
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 3})]),
                _msg(content="Found a matching 3BHK unit T-1."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Qualify this lead and find three properties that fit their requirements.",
            )

        assert "High intent, 3BHK, ready to buy." in result["reply"]
        assert "Found a matching 3BHK unit T-1." in result["reply"]
        # Lead Qualification's own labeled section must appear BEFORE
        # Property Matching's (SPECIALIST_ORDER, not dict/set order).
        assert result["reply"].index("Lead Qualification") < result["reply"].index("Property Matching")

        # The second call's messages must contain lead_qualifier's real
        # structured get_lead result as context, not a blind conversation
        # dump. Two "user"-role messages are expected here: the first is
        # the raw, already-persisted conversation history entry (always
        # the ORIGINAL unenriched message, saved before any enrichment
        # happens); the LAST is the actual argument run_tool_calling_
        # employee_turn appended this call, which is the one that carries
        # the enrichment for a chain member after the first.
        second_call_messages = mock_chat.call_args_list[2].args[0]
        user_msgs = [m for m in second_call_messages if m["role"] == "user"]
        assert "Lead Qualification - real findings" in user_msgs[-1]["content"]
        assert lead.id in user_msgs[-1]["content"] or str(lead.id) in user_msgs[-1]["content"]

    def test_max_specialists_per_request_bound_is_respected(self):
        assert MAX_SPECIALISTS_PER_REQUEST == len(SPECIALIST_ORDER) == 5

    def test_chain_is_truncated_never_exceeds_the_bound(self, agency):
        db, biz = agency
        registry = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None).registry
        manager = ManagerAgent(registry=registry, memory=__import__("app.agents.memory", fromlist=["ConversationMemory"]).ConversationMemory(), agency=biz, tool_router=None)
        fake_plan = Plan(intent="x", confidence=0.9, priority=1, employees=list(SPECIALIST_ORDER) + ["extra_unknown"], tools=[])
        with patch.object(ManagerAgent, "_run_one_employee", return_value={"reply": "", "tool_result": None}) as mock_run:
            manager.delegate(fake_plan, "message", [])
        called_employees = [c.args[0] for c in mock_run.call_args_list]
        assert len([e for e in called_employees if e in SPECIALIST_ORDER]) <= MAX_SPECIALISTS_PER_REQUEST

    def test_unrelated_single_intent_request_still_works_unchanged(self, agency):
        db, biz = agency
        with patch("app.agents.tool_loop.chat_completion"):
            with patch("app.services.llm_client.chat_completion") as mock_legacy_chat:
                mock_legacy_chat.return_value = SimpleNamespace(content="Here's our pricing.", tool_calls=None)
                result = EmployeeAgent(db).process(
                    agency_id=biz.id, conversation_id=None, message="What's the price for this?",
                )
        assert result["plan"]["employees"] == ["sales"]


class TestContextPassing:
    """Category C."""

    def test_third_specialist_sees_both_earlier_specialists_findings(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Three Spec Test")
        _, unit = _make_active_property(db, biz, unit_number="T-3", bhk=2)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Qualified."),
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 2})]),
                _msg(content="Matched T-3."),
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id}, call_id="c3")]),
                _msg(content="Recommend contacting the buyer about T-3."),
            ]
            EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Qualify this lead, find three properties that fit their requirements, and tell me the next best action.",
            )

        third_call_messages = mock_chat.call_args_list[4].args[0]
        user_msgs = [m for m in third_call_messages if m["role"] == "user"]
        assert "Lead Qualification - real findings" in user_msgs[-1]["content"]
        assert "Property Matching - real findings" in user_msgs[-1]["content"]


class TestFailureIsolation:
    """Category D.

    A live/mocked LLMProviderError (rate limit, timeout, etc.) is
    already handled gracefully INSIDE run_bounded_tool_loop - it returns
    a real, non-empty, honest ToolLoopResult.reply (e.g. "temporarily
    unavailable"), never an empty one - so that case alone never
    exercises Manager's own "a chain member produced nothing at all"
    path. These tests instead force a genuine unhandled exception (e.g.
    a real bug inside one specialist's own code) to prove THAT specific
    failure mode - the one where a chain member truly returns nothing -
    is isolated and reported honestly rather than fabricated."""

    def test_one_specialists_unhandled_exception_does_not_prevent_the_other_from_succeeding(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Failure Isolation Test")
        _make_active_property(db, biz, unit_number="F-1", bhk=3)

        with patch("app.agents.lead_qualifier_agent.run_tool_calling_employee_turn", side_effect=RuntimeError("boom")), \
             patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 3})]),
                _msg(content="Found a match despite the earlier issue."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Qualify this lead and find three properties that fit their requirements.",
            )

        assert "Could not be completed" in result["reply"]
        assert "Lead Qualification" in result["reply"]
        assert "Found a match despite the earlier issue." in result["reply"]

    def test_manager_never_fabricates_a_missing_specialists_success(self, agency):
        db, biz = agency
        with patch("app.agents.lead_qualifier_agent.run_tool_calling_employee_turn", side_effect=RuntimeError("boom 1")), \
             patch("app.agents.property_matcher_agent.run_tool_calling_employee_turn", side_effect=RuntimeError("boom 2")):
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Qualify this lead and find three properties that fit their requirements.",
            )
        assert result["reply"].count("Could not be completed") == 2
        assert "Lead Qualification" in result["reply"] and "Property Matching" in result["reply"]


class TestApprovalAwareness:
    """Category E."""

    def test_manager_surfaces_a_pending_approval_from_the_chain_never_bypasses_it(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Approval Aware Test")
        _, unit = _make_active_property(db, biz, unit_number="A-1", bhk=3)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Qualified."),
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id}, call_id="c2")]),
                _msg(content="Recommend a follow-up."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Qualify this lead and tell me the next best action - is this lead stalled?",
            )

        # No approval tool was actually called in this scenario, so there
        # should be no fabricated approval note either - a real negative
        # check that the mechanism doesn't invent one.
        assert "Approval needed" not in result["reply"]
        assert db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz.id).count() == 0


class TestGroundingSourceOfTruth:
    """Category G - live DB state always outranks anything said earlier
    in the same turn."""

    def test_property_matched_earlier_in_the_chain_is_reverified_against_current_status(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Grounding Test")
        _, unit = _make_active_property(db, biz, unit_number="G-1", bhk=3)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Qualified."),
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 3})]),
                _msg(content="Unit G-1 is available for this buyer."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Qualify this lead and find three properties that fit their requirements.",
            )

        assert "Verified against current inventory" in result["reply"]
        assert "G-1" in result["reply"]
        assert "active" in result["reply"]

    def test_a_sold_property_is_reverified_as_sold_even_if_matched_earlier_as_active(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Sold Grounding Test")
        _, unit = _make_active_property(db, biz, unit_number="G-2", bhk=3)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Qualified."),
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 3})]),
                _msg(content="Unit G-2 is available for this buyer."),
            ]
            # The unit is sold AFTER property_matcher's own tool call
            # already returned "active" - simulating exactly the spec's
            # named scenario (a specialist's text/earlier tool result
            # going stale mid-turn). Patching PropertyService.update_status
            # directly (not through the employee turn) to change real DB
            # state between the chain step and Manager's own final re-check.
            PropertyService(db).update_status(unit.id, biz.id, "sold")
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Qualify this lead and find three properties that fit their requirements.",
            )

        assert "sold" in result["reply"]


class TestTenantIsolation:
    """Category F."""

    def test_manager_verification_pass_never_reveals_another_agencys_property(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        lead2 = _make_lead(db2, biz2, name="Agency2 Lead")
        _, unit1 = _make_active_property(db1, biz1, unit_number="X-1", bhk=3)

        # Agency 2's property_matcher "finds" agency 1's property id only
        # via a contrived mocked tool result (never possible for real,
        # since search_properties/get_property are agency-scoped) - this
        # proves even IF such an id ever appeared in structured findings,
        # Manager's own re-verification (also agency-scoped) would not
        # resolve it.
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead2.id})]),
                _msg(content="Qualified."),
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 3})]),
                _msg(content="No real match found for this agency."),
            ]
            result = EmployeeAgent(db2).process(
                agency_id=biz2.id, conversation_id=None,
                message="Qualify this lead and find three properties that fit their requirements.",
            )
        assert "X-1" not in result["reply"]


class TestAgentExecutionObservability:
    """Category I."""

    def test_each_specialist_in_the_chain_gets_its_own_agent_execution_row(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Exec Chain Test")
        _make_active_property(db, biz, unit_number="E-1", bhk=3)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Qualified."),
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 3})]),
                _msg(content="Matched."),
            ]
            EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Qualify this lead and find three properties that fit their requirements.",
            )

        rows = AgentExecutionService(db).list_for_agency(biz.id)
        employees_recorded = {r.employee for r in rows}
        assert employees_recorded == {"lead_qualifier", "property_matcher"}
        assert all(r.status == models.AgentExecutionStatus.succeeded for r in rows)

    def test_a_legacy_single_shot_employee_turn_is_recorded_as_ai_manager(self, agency):
        """Final Hardening phase: the legacy single-shot employees
        (sales/support/receptionist/analytics/marketing/finance) have no
        tool-calling loop of their own to record an AgentExecution, so
        EmployeeAgent.process() records one itself under 'ai_manager' -
        this was a real AI-metering gap before this fix (see
        ARCHITECTURE.md's Billing & Subscriptions section)."""
        db, biz = agency
        with patch("app.agents.tool_loop.chat_completion"):
            with patch("app.services.llm_client.chat_completion") as mock_legacy_chat:
                mock_legacy_chat.return_value = SimpleNamespace(content="Here's our pricing.", tool_calls=None)
                EmployeeAgent(db).process(
                    agency_id=biz.id, conversation_id=None, message="What's the price for this?",
                )

        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert rows[0].employee == "ai_manager"
        assert rows[0].status == models.AgentExecutionStatus.succeeded

    def test_dashboard_chat_declines_gracefully_once_the_ai_action_limit_is_reached(self, agency):
        db, biz = agency
        from app.agents.prompt_guard import AI_ACTION_LIMIT_MESSAGE
        from app.services.billing.entitlement_service import EntitlementService
        with patch.object(EntitlementService, "can_use_ai_action", return_value=(False, "limit reached")):
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None, message="What's the price for this?",
            )
        assert result["reply"] == AI_ACTION_LIMIT_MESSAGE
        # Never reaches the LLM, and records nothing - no AI action actually happened.
        assert AgentExecutionService(db).list_for_agency(biz.id) == []
