"""
Phase 10C, Agent #1: the Real Estate Sales AI employee
(app.agents.real_estate_sales_agent.RealEstateSalesAgent), exercised
through the REAL, existing architecture end-to-end: EmployeeAgent.
process() -> AIOrchestrator -> Planner -> ManagerAgent.delegate() ->
RealEstateSalesAgent.respond() -> run_bounded_tool_loop -> ToolRouter ->
the real Phase 10A-10C tools -> the real dev database.

Registered under "real_estate_sales", NOT "sales" - confirms the legacy
generic SalesAgent (registry key "sales") is completely unaffected.

Only chat_completion is mocked - zero real LLM tokens.

Run: python3 -m pytest tests/test_real_estate_sales_agent.py -q   (from backend/)
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
from app.agents.orchestrator import AIOrchestrator
from app.agents.sales_agent import SalesAgent
from app.agents.tool_router import ToolRouter
from app.services.ai_workforce.execution_service import AgentExecutionService
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"RE Sales Test {suffix}",
        slug=f"re-sales-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@resalestest.example",
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


def _make_active_property(db, agency, *, unit_number="U-1", bhk=3):
    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="RE Sales Project", city="Pune"))
    ProjectService(db).update(project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
    unit = PropertyService(db).create(
        agency.id,
        schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=bhk,
            carpet_area_sqft=Decimal("1200.00"), price=Decimal("9500000.00"), unit_number=unit_number,
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


class TestArchitectureDecisionDoesNotBreakLegacySales:
    def test_legacy_sales_key_still_resolves_to_the_original_generic_agent(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        assert isinstance(orch.registry.get_employee("sales"), SalesAgent)
        assert orch.registry.employee_tools("sales") == ["lead", "knowledge_search"]
        assert orch.registry.employee_is_tool_calling("sales") is False

    def test_real_estate_sales_is_a_separate_registered_employee(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        assert orch.registry.get_employee("real_estate_sales") is not None
        assert orch.registry.employee_is_tool_calling("real_estate_sales") is True
        assert set(orch.registry.employee_tools("real_estate_sales")) == {
            "get_lead", "get_property", "search_properties", "get_project",
            "get_lead_appointments", "get_lead_bookings", "update_lead_qualification",
            "draft_customer_message", "knowledge_search",
        }

    def test_real_estate_sales_is_never_granted_booking_or_send_tools(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        forbidden = {"propose_visit", "confirm_visit", "reschedule_visit", "cancel_visit", "propose_send_customer_message"}
        assert forbidden.isdisjoint(set(orch.registry.employee_tools("real_estate_sales")))


class TestPlannerRouting:
    def test_next_best_action_message_reaches_real_estate_sales_end_to_end(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Rahul", status="contacted")

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Next best action: send a follow-up, the lead has gone quiet."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="What's the next best action for this lead?",
            )

        assert result["plan"]["intent"] == "real_estate_sales"
        assert result["plan"]["employees"] == ["real_estate_sales"]
        assert "Next best action" in result["reply"]


class TestToolPermissionGate:
    def test_unauthorized_mutation_tools_are_forbidden_and_never_execute(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        for forbidden_tool in ("propose_visit", "confirm_visit", "reschedule_visit", "cancel_visit", "propose_send_customer_message"):
            result = router.execute(employee="real_estate_sales", tool_name=forbidden_tool, message="x")
            assert result == {
                "success": False, "error": "forbidden",
                "message": f"Employee 'real_estate_sales' not permitted to use tool '{forbidden_tool}'.",
            }
        assert db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz.id).count() == 0


class TestLeadAndPropertyContext:
    def test_get_lead_and_get_property_return_real_data(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Context Test", budget="1.2 Cr")
        _, unit = _make_active_property(db, biz, unit_number="S-1")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)

        lead_result = router.execute(employee="real_estate_sales", tool_name="get_lead", message="x", lead_id=lead.id)
        assert lead_result["result"]["lead"]["budget"] == "1.2 Cr"

        prop_result = router.execute(employee="real_estate_sales", tool_name="get_property", message="x", property_id=unit.id)
        assert prop_result["result"]["property"]["unit_number"] == "S-1"

    def test_get_lead_appointments_and_bookings_are_empty_for_a_fresh_lead(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Fresh Lead")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        appts = router.execute(employee="real_estate_sales", tool_name="get_lead_appointments", message="x", lead_id=lead.id)
        bookings = router.execute(employee="real_estate_sales", tool_name="get_lead_bookings", message="x", lead_id=lead.id)
        assert appts["result"] == {"success": True, "count": 0, "appointments": []}
        assert bookings["result"] == {"success": True, "count": 0, "bookings": []}


class TestNextBestActionAndDraftCreation:
    def test_model_recommendation_and_draft_are_grounded_in_real_tool_results(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Priya", status="qualified", qualification_score=80)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="", tool_calls=[_tool_call("draft_customer_message", {
                    "lead_id": lead.id, "message_body": "Hi Priya, following up on your inquiry.",
                }, call_id="c2")]),
                _msg(content="Recommended: send a follow-up. I've drafted a message for review."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="What's the next best action for this lead?",
            )

        assert "Recommended" in result["reply"]
        pending = db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz.id).all()
        assert len(pending) == 1
        assert pending[0].action_type == "customer_message_draft"
        assert pending[0].payload["draft"] == "Hi Priya, following up on your inquiry."
        assert pending[0].requested_by_employee == "real_estate_sales"


class TestUnauthorizedMutationsNeverExecute:
    def test_a_model_that_tries_a_forbidden_tool_is_refused_not_executed(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Blocked Attempt")

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("propose_visit", {
                    "lead_id": lead.id, "property_id": "whatever", "start_local_iso": "2026-10-01T11:00",
                })]),
                _msg(content="I can't schedule that myself - please ask Site Visit."),
            ]
            EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="What's the next best action for this lead?",
            )

        assert db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz.id).count() == 0


class TestTenantIsolation:
    def test_cannot_read_another_agencys_lead(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        lead1 = _make_lead(db1, biz1, name="Agency1 Lead")
        orch2 = AIOrchestrator(db=db2, agency=biz2, conversation=None, lead=None)
        router2 = ToolRouter(orch2.registry, db=db2, agency=biz2)
        result = router2.execute(employee="real_estate_sales", tool_name="get_lead", message="x", lead_id=lead1.id)
        assert result["result"] == {"success": False, "error": "lead_not_found"}

    def test_cannot_read_another_agencys_property(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _, unit1 = _make_active_property(db1, biz1, unit_number="A-1")
        orch2 = AIOrchestrator(db=db2, agency=biz2, conversation=None, lead=None)
        router2 = ToolRouter(orch2.registry, db=db2, agency=biz2)
        result = router2.execute(employee="real_estate_sales", tool_name="get_property", message="x", property_id=unit1.id)
        assert result["result"] == {"success": False, "error": "property_not_found"}


class TestAgentExecutionRecording:
    def test_successful_turn_records_agent_execution(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Exec Test")
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Recommend contacting the buyer."),
            ]
            EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None, message="What's the next best action for this lead?",
            )
        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert rows[0].employee == "real_estate_sales"
        assert rows[0].status == models.AgentExecutionStatus.succeeded
