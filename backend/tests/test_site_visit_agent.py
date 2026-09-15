"""
Phase 10C, Agent #2: the Site Visit AI employee
(app.agents.site_visit_agent.SiteVisitAgent), exercised through the
real, existing architecture end-to-end. Every scheduling action goes
through app.services.scheduling.appointment_service.AppointmentService -
never a second scheduling system, never a direct Appointment ORM
mutation from a tool.

Only chat_completion is mocked - zero real LLM tokens.

Run: python3 -m pytest tests/test_site_visit_agent.py -q   (from backend/)
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models
from app.agents.employee_agent import EmployeeAgent
from app.agents.orchestrator import AIOrchestrator
from app.agents.tool_router import ToolRouter
from app.services.ai_workforce.execution_service import AgentExecutionService
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import now_utc, to_local


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Site Visit Test {suffix}",
        slug=f"site-visit-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@sitevisittest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _book_real_appointment(db, agency, *, phone="9000000010"):
    svc = AppointmentService(db)
    svc.ensure_defaults(agency)
    start_local = (to_local(now_utc(), agency.timezone) + dt.timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
    outcome = svc.book(
        agency, start_local_iso=start_local.strftime("%Y-%m-%dT%H:%M"),
        customer_name="Site Visit Buyer", customer_phone=phone, customer_email=None,
    )
    assert outcome.ok, outcome.message
    return outcome.appointment


def _cleanup(db, agency):
    db.query(models.AgentExecution).filter(models.AgentExecution.agency_id == agency.id).delete()
    db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == agency.id).delete()
    db.query(models.Message).filter(
        models.Message.conversation_id.in_(
            db.query(models.Conversation.id).filter(models.Conversation.agency_id == agency.id)
        )
    ).delete(synchronize_session=False)
    db.query(models.Conversation).filter(models.Conversation.agency_id == agency.id).delete()
    db.query(models.Appointment).filter(models.Appointment.agency_id == agency.id).delete()
    db.query(models.Lead).filter(models.Lead.agency_id == agency.id).delete()
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


class TestEmployeeRegistration:
    def test_site_visit_is_registered_and_tool_calling(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        assert orch.registry.get_employee("site_visit") is not None
        assert orch.registry.employee_is_tool_calling("site_visit") is True
        assert set(orch.registry.employee_tools("site_visit")) == {
            "get_lead", "get_property", "get_available_slots",
            "propose_visit", "confirm_visit", "reschedule_visit", "cancel_visit",
            "get_lead_appointments", "knowledge_search",
        }


class TestPlannerRouting:
    def test_site_visit_message_reaches_site_visit_employee(self, agency):
        db, biz = agency
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_available_slots", {"date_local": "2026-10-05"})]),
                _msg(content="Here are the open site-visit slots."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Can we schedule a site visit? Show me availability.",
            )
        assert "site_visit" in result["plan"]["employees"]


class TestAvailableSlotRetrieval:
    def test_get_available_slots_returns_real_slots(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        tomorrow = (to_local(now_utc(), biz.timezone) + dt.timedelta(days=1)).date().isoformat()
        result = router.execute(employee="site_visit", tool_name="get_available_slots", message="x", date_local=tomorrow)
        assert result["result"]["success"] is True
        assert len(result["result"]["slots"]) > 0

    def test_invalid_date_is_rejected_not_crashed(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(employee="site_visit", tool_name="get_available_slots", message="x", date_local="not-a-date")
        assert result["result"] == {"success": False, "error": "invalid_date", "message": "date_local must be YYYY-MM-DD."}


class TestActualAppointmentStateGrounding:
    def test_get_lead_appointments_reflects_the_real_status(self, agency):
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        lead_id = None  # this appointment has no lead - test the read path directly on a lead-linked one below
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        # Link it to a real lead to test the by-lead read tool.
        lead = models.Lead(agency_id=biz.id, status="new", name="Visit Lead")
        db.add(lead); db.commit(); db.refresh(lead)
        appt.lead_id = lead.id
        db.commit()

        result = router.execute(employee="site_visit", tool_name="get_lead_appointments", message="x", lead_id=lead.id)
        assert result["result"]["success"] is True
        assert result["result"]["appointments"][0]["status"] == "scheduled"

    def test_status_after_a_real_cancel_is_cancelled_not_scheduled(self, agency):
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        AppointmentService(db).cancel(biz, appt.id)
        lead = models.Lead(agency_id=biz.id, status="new", name="Cancelled Visit Lead")
        db.add(lead); db.commit(); db.refresh(lead)
        db.refresh(appt)
        appt.lead_id = lead.id
        db.commit()

        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(employee="site_visit", tool_name="get_lead_appointments", message="x", lead_id=lead.id)
        assert result["result"]["appointments"][0]["status"] == "cancelled"


class TestSchedulingProposalsNeverMutateDirectly:
    def test_propose_visit_creates_only_a_pending_approval(self, agency):
        db, biz = agency
        lead = models.Lead(agency_id=biz.id, status="new", name="Propose Test")
        db.add(lead); db.commit(); db.refresh(lead)
        from app.services.inventory.project_service import ProjectService
        from app.services.inventory.property_service import PropertyService
        from app import schemas as app_schemas
        from decimal import Decimal
        project = ProjectService(db).create(biz.id, app_schemas.ProjectCreate(name="Visit Project", city="Pune"))
        ProjectService(db).update(project.id, biz.id, app_schemas.ProjectUpdate(project_status="active"))
        unit = PropertyService(db).create(biz.id, app_schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=2,
            carpet_area_sqft=Decimal("900.00"), price=Decimal("6000000.00"), unit_number="V-1",
        ))
        PropertyService(db).update_status(unit.id, biz.id, "active")

        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        tomorrow = (to_local(now_utc(), biz.timezone) + dt.timedelta(days=1)).strftime("%Y-%m-%dT11:00")
        result = router.execute(
            employee="site_visit", tool_name="propose_visit", message="x",
            lead_id=lead.id, property_id=unit.id, start_local_iso=tomorrow, requested_by_employee="site_visit",
        )
        assert result["result"]["success"] is True
        assert db.query(models.Appointment).filter(models.Appointment.agency_id == biz.id).count() == 0

        db.query(models.Property).filter(models.Property.agency_id == biz.id).delete()
        db.query(models.Project).filter(models.Project.agency_id == biz.id).delete()
        db.commit()

    def test_confirm_reschedule_cancel_all_only_propose(self, agency):
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)

        for tool_name, extra in [
            ("confirm_visit", {}),
            ("reschedule_visit", {"new_start_local_iso": (to_local(now_utc(), biz.timezone) + dt.timedelta(days=2)).strftime("%Y-%m-%dT11:00")}),
            ("cancel_visit", {}),
        ]:
            result = router.execute(
                employee="site_visit", tool_name=tool_name, message="x",
                appointment_id=appt.id, requested_by_employee="site_visit", **extra,
            )
            assert result["result"]["success"] is True
            assert result["result"]["proposed"] is True

        db.refresh(appt)
        assert appt.status == models.AppointmentStatus.scheduled, "none of confirm/reschedule/cancel proposals may mutate the real appointment"
        pending = db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz.id).all()
        assert {p.action_type for p in pending} == {"confirm_site_visit", "reschedule_site_visit", "cancel_site_visit"}

    def test_reschedule_with_invalid_datetime_is_rejected(self, agency):
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(
            employee="site_visit", tool_name="reschedule_visit", message="x",
            appointment_id=appt.id, new_start_local_iso="not-a-datetime",
        )
        assert result["result"] == {"success": False, "error": "invalid_datetime"}


class TestToolPermissionGate:
    def test_search_properties_and_send_message_are_forbidden(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        for forbidden_tool in ("search_properties", "search_projects", "propose_send_customer_message", "update_lead_qualification"):
            result = router.execute(employee="site_visit", tool_name=forbidden_tool, message="x")
            assert result["success"] is False and result["error"] == "forbidden"


class TestTenantIsolation:
    def test_cannot_confirm_another_agencys_appointment(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        appt1 = _book_real_appointment(db1, biz1)
        orch2 = AIOrchestrator(db=db2, agency=biz2, conversation=None, lead=None)
        router2 = ToolRouter(orch2.registry, db=db2, agency=biz2)
        result = router2.execute(employee="site_visit", tool_name="confirm_visit", message="x", appointment_id=appt1.id)
        assert result["result"] == {"success": False, "error": "appointment_not_found"}
        db1.refresh(appt1)
        assert appt1.status == models.AppointmentStatus.scheduled


class TestAgentExecutionRecording:
    def test_successful_turn_records_agent_execution(self, agency):
        db, biz = agency
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_available_slots", {"date_local": "2026-10-05"})]),
                _msg(content="Here are the open slots."),
            ]
            EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None, message="Can we schedule a site visit?",
            )
        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert rows[0].employee == "site_visit"
        assert rows[0].status == models.AgentExecutionStatus.succeeded

    def test_malformed_tool_args_do_not_crash_and_provider_failure_is_recorded_failed(self, agency):
        db, biz = agency
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[SimpleNamespace(
                    id="c1", function=SimpleNamespace(name="get_available_slots", arguments="{bad json"),
                )]),
                _msg(content="Let me try again - could you confirm the date?"),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None, message="Can we schedule a site visit?",
            )
        assert result["reply"]

        from app.services.llm.base import LLMProviderError
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = LLMProviderError("provider_error", "temporarily unavailable")
            EmployeeAgent(db).process(agency_id=biz.id, conversation_id=None, message="Can we schedule a site visit?")
        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert rows[0].status == models.AgentExecutionStatus.failed
