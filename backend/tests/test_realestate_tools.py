"""
Phase 10A, Step 10 test harness - categories A (tool permission) and B
(tenant isolation), plus functional correctness of the new real-estate
AI-workforce tools (app/tools/realestate_lead_property_tools.py,
app/tools/realestate_visit_followup_tools.py) via the real
Registry/ToolRouter permission gate - the exact same mechanism every
existing tool already goes through.

Against the real dev database with real throwaway rows, cleaned up
after each test - the same convention test_phase9_conversion.py already
uses. Zero LLM tokens (nothing here calls chat_completion).

Run: python3 -m pytest tests/test_realestate_tools.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app import models, schemas
from app.agents.registry import Registry
from app.agents.tool_router import ToolRouter
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.lead_service import LeadService
from app.services.ai_workforce.approval_service import AIActionApprovalService
from app.tools.realestate_lead_property_tools import (
    GetLeadTool, UpdateLeadQualificationTool, SearchPropertiesTool, SearchProjectsTool, GetPropertyTool,
)
from app.tools.realestate_visit_followup_tools import (
    GetAvailableSlotsTool, ProposeVisitTool, ConfirmVisitTool, CreateFollowUpTool, DraftCustomerMessageTool,
)

ALL_TOOL_NAMES = [
    "get_lead", "update_lead_qualification", "search_properties", "search_projects", "get_property",
    "get_available_slots", "propose_visit", "confirm_visit", "create_follow_up", "draft_customer_message",
]


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"RE Tools Test {suffix}",
        slug=f"re-tools-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@retoolstest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_active_property(db, agency, *, unit_number="U-1"):
    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="RE Tools Project", city="Pune"))
    ProjectService(db).update(project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
    unit = PropertyService(db).create(
        agency.id,
        schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=3,
            carpet_area_sqft=Decimal("1200.00"), price=Decimal("9500000.00"), unit_number=unit_number,
        ),
    )
    PropertyService(db).update_status(unit.id, agency.id, "active")
    return project, unit


def _make_lead(db, agency, **fields):
    fields.setdefault("status", "new")
    lead = models.Lead(agency_id=agency.id, **fields)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _cleanup(db, agency):
    db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == agency.id).delete()
    db.query(models.AgentExecution).filter(models.AgentExecution.agency_id == agency.id).delete()
    db.query(models.Appointment).filter(models.Appointment.agency_id == agency.id).delete()
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


def _full_registry(db):
    """Registers every new real-estate tool AND a tool-calling-capable
    "re_agent" employee granted all of them, plus a second employee
    granted none - so permission-gate tests have something to assert
    both "allowed" and "forbidden" against."""
    registry = Registry(db=db)
    registry.register_tool("get_lead", GetLeadTool(db=db))
    registry.register_tool("update_lead_qualification", UpdateLeadQualificationTool(db=db))
    registry.register_tool("search_properties", SearchPropertiesTool(db=db))
    registry.register_tool("search_projects", SearchProjectsTool(db=db))
    registry.register_tool("get_property", GetPropertyTool(db=db))
    registry.register_tool("get_available_slots", GetAvailableSlotsTool(db=db))
    registry.register_tool("propose_visit", ProposeVisitTool(db=db))
    registry.register_tool("confirm_visit", ConfirmVisitTool(db=db))
    registry.register_tool("create_follow_up", CreateFollowUpTool(db=db))
    registry.register_tool("draft_customer_message", DraftCustomerMessageTool(db=db))
    registry.register_employee("re_agent", instance=object(), tools=ALL_TOOL_NAMES, tool_calling=True)
    registry.register_employee("receptionist_only", instance=object(), tools=["get_available_slots"])
    return registry


class TestToolPermissionGate:
    def test_granted_tool_executes(self, agency):
        db, biz = agency
        registry = _full_registry(db)
        router = ToolRouter(registry, db=db, agency=biz)
        result = router.execute(employee="re_agent", tool_name="search_projects", message="x")
        assert result["success"] is True

    def test_ungranted_tool_is_forbidden_and_never_executes(self, agency):
        db, biz = agency
        registry = _full_registry(db)
        router = ToolRouter(registry, db=db, agency=biz)
        result = router.execute(employee="receptionist_only", tool_name="propose_visit", message="x", lead_id="whatever")
        assert result == {"success": False, "error": "forbidden", "message": "Employee 'receptionist_only' not permitted to use tool 'propose_visit'."}
        # Forbidden means never even attempted - no approval row was created.
        assert AIActionApprovalService(db).list_pending(biz.id) == []

    def test_unregistered_tool_name_is_rejected_before_any_permission_check(self, agency):
        db, biz = agency
        registry = _full_registry(db)
        router = ToolRouter(registry, db=db, agency=biz)
        result = router.execute(employee="re_agent", tool_name="delete_everything", message="x")
        assert result["success"] is False
        assert result["error"] == "tool_not_found"

    def test_capability_flag_defaults_to_false_for_legacy_employees(self, agency):
        db, biz = agency
        registry = _full_registry(db)
        assert registry.employee_is_tool_calling("re_agent") is True
        assert registry.employee_is_tool_calling("receptionist_only") is False
        assert registry.employee_is_tool_calling("nonexistent") is False


class TestTenantIsolationAcrossNewTools:
    def test_get_property_never_returns_another_agencys_unit(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _, unit1 = _make_active_property(db1, biz1, unit_number="A-101")
        registry2 = _full_registry(db2)
        router2 = ToolRouter(registry2, db=db2, agency=biz2)

        result = router2.execute(employee="re_agent", tool_name="get_property", message="x", property_id=unit1.id)
        assert result["success"] is True
        assert result["result"]["success"] is False
        assert result["result"]["error"] == "property_not_found"

    def test_search_properties_never_leaks_another_agencys_inventory(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _make_active_property(db1, biz1, unit_number="A-101")
        _make_active_property(db2, biz2, unit_number="B-202")

        registry1 = _full_registry(db1)
        result = ToolRouter(registry1, db=db1, agency=biz1).execute(
            employee="re_agent", tool_name="search_properties", message="x",
        )
        units = [p["unit_number"] for p in result["result"]["properties"]]
        assert units == ["A-101"]

    def test_get_lead_never_returns_another_agencys_lead(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        lead1 = _make_lead(db1, biz1, name="Cross Tenant Test")
        registry2 = _full_registry(db2)

        result = ToolRouter(registry2, db=db2, agency=biz2).execute(
            employee="re_agent", tool_name="get_lead", message="x", lead_id=lead1.id,
        )
        assert result["result"]["success"] is False
        assert result["result"]["error"] == "lead_not_found"

    def test_propose_visit_rejects_a_lead_id_from_another_agency(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        lead1 = _make_lead(db1, biz1, name="Cross Tenant Lead")
        _, unit2 = _make_active_property(db2, biz2, unit_number="B-202")
        registry2 = _full_registry(db2)

        result = ToolRouter(registry2, db=db2, agency=biz2).execute(
            employee="re_agent", tool_name="propose_visit", message="x",
            lead_id=lead1.id, property_id=unit2.id, start_local_iso="2026-10-01T11:00",
        )
        assert result["result"]["success"] is False
        assert result["result"]["error"] == "lead_not_found"
        # No approval was created for agency 2 off the back of another tenant's lead id.
        assert AIActionApprovalService(db2).list_pending(biz2.id) == []


class TestReadToolsReturnRealData:
    def test_get_property_returns_the_real_stored_price(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz, unit_number="C-303")
        registry = _full_registry(db)
        result = ToolRouter(registry, db=db, agency=biz).execute(
            employee="re_agent", tool_name="get_property", message="x", property_id=unit.id,
        )
        assert result["result"]["success"] is True
        assert result["result"]["property"]["price"] == 9500000.0
        assert result["result"]["property"]["unit_number"] == "C-303"

    def test_search_properties_with_malformed_price_filter_returns_invalid_arguments_not_a_crash(self, agency):
        db, biz = agency
        registry = _full_registry(db)
        result = ToolRouter(registry, db=db, agency=biz).execute(
            employee="re_agent", tool_name="search_properties", message="x", min_price="not-a-number",
        )
        assert result["success"] is True  # ToolRouter itself never crashes
        assert result["result"]["success"] is False
        assert result["result"]["error"] == "invalid_arguments"

    def test_get_lead_returns_missing_lead_id_error_when_absent(self, agency):
        db, biz = agency
        registry = _full_registry(db)
        result = ToolRouter(registry, db=db, agency=biz).execute(employee="re_agent", tool_name="get_lead", message="x")
        assert result["result"] == {"success": False, "error": "missing_lead_id"}


class TestUpdateLeadQualification:
    def test_valid_status_updates_the_real_lead(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Qualify Me")
        registry = _full_registry(db)
        result = ToolRouter(registry, db=db, agency=biz).execute(
            employee="re_agent", tool_name="update_lead_qualification", message="x", lead_id=lead.id, status="qualified",
        )
        assert result["result"]["success"] is True
        db.refresh(lead)
        assert lead.status == "qualified"

    def test_unknown_status_is_rejected_and_lead_is_unchanged(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Qualify Me", status="new")
        registry = _full_registry(db)
        result = ToolRouter(registry, db=db, agency=biz).execute(
            employee="re_agent", tool_name="update_lead_qualification", message="x", lead_id=lead.id, status="super duper hot lead",
        )
        assert result["result"]["success"] is False
        assert result["result"]["error"] == "invalid_status"
        db.refresh(lead)
        assert lead.status == "new"


class TestApprovalGatedToolsNeverMutateRealState:
    def test_propose_visit_creates_only_a_pending_approval_no_appointment(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Visit Proposer", phone="9000000001")
        _, unit = _make_active_property(db, biz, unit_number="D-404")
        registry = _full_registry(db)

        result = ToolRouter(registry, db=db, agency=biz).execute(
            employee="re_agent", tool_name="propose_visit", message="x",
            lead_id=lead.id, property_id=unit.id, start_local_iso="2026-10-05T11:00",
            requested_by_employee="re_agent",
        )
        assert result["result"]["success"] is True
        assert result["result"]["proposed"] is True

        appts = db.query(models.Appointment).filter(models.Appointment.agency_id == biz.id).all()
        assert appts == [], "propose_visit must never create a real Appointment"

        pending = AIActionApprovalService(db).list_pending(biz.id)
        assert len(pending) == 1
        assert pending[0].action_type == "schedule_site_visit"
        assert pending[0].requested_by_employee == "re_agent"
        assert pending[0].payload["property_id"] == str(unit.id)

    def test_draft_customer_message_never_sends_anything(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Draft Target")
        registry = _full_registry(db)

        result = ToolRouter(registry, db=db, agency=biz).execute(
            employee="re_agent", tool_name="draft_customer_message", message="x",
            lead_id=lead.id, message_body="Hi! Following up on your inquiry.",
        )
        assert result["result"]["success"] is True
        pending = AIActionApprovalService(db).list_pending(biz.id)
        assert len(pending) == 1
        assert pending[0].action_type == "customer_message_draft"
        assert pending[0].payload["draft"] == "Hi! Following up on your inquiry."

    def test_confirm_visit_does_not_change_the_real_appointment_status(self, agency):
        db, biz = agency
        from app.services.scheduling.appointment_service import AppointmentService
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        from app.services.scheduling.datetime_utils import now_utc, to_local
        import datetime as dt
        start_local = to_local(now_utc(), biz.timezone) + dt.timedelta(days=1)
        while start_local.weekday() == 6:  # demo business hours are closed Sundays
            start_local += dt.timedelta(days=1)
        start_local = start_local.replace(hour=12, minute=0, second=0, microsecond=0)
        booked = svc.book(biz, start_local_iso=start_local.strftime("%Y-%m-%dT%H:%M"),
                           customer_name="Confirm Me", customer_phone="9000000002", customer_email=None)
        assert booked.ok is True
        appt_id = booked.appointment.id

        registry = _full_registry(db)
        result = ToolRouter(registry, db=db, agency=biz).execute(
            employee="re_agent", tool_name="confirm_visit", message="x", appointment_id=appt_id,
        )
        assert result["result"]["success"] is True
        db.refresh(booked.appointment)
        assert booked.appointment.status == models.AppointmentStatus.scheduled, "confirm_visit must not change real Appointment status"

        pending = AIActionApprovalService(db).list_pending(biz.id)
        assert len(pending) == 1
        assert pending[0].action_type == "confirm_site_visit"


class TestToolRouterRollsBackAfterADbLevelToolFailure:
    """Phase 10C live-smoke-test finding: a real Groq call passed a
    property's unit_number string ("G-0701") as property_id instead of
    its real UUID - PropertyService.get()'s raw query then raised
    psycopg2.errors.InvalidTextRepresentation, which Postgres responds
    to by aborting the whole transaction. ToolRouter.execute() already
    caught the exception (no crash), but never rolled back, so every
    later query on the SAME session/request - a further tool call in
    the same bounded-loop turn, or AgentExecution recording afterward -
    would also fail with "current transaction is aborted", even though
    nothing about them was wrong. Fixed by rolling back inside
    ToolRouter.execute()'s except block."""

    def test_a_non_uuid_id_argument_fails_cleanly_and_the_session_stays_usable(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz, unit_number="G-0701")
        registry = _full_registry(db)
        router = ToolRouter(registry, db=db, agency=biz)

        # Exactly the real live failure: a unit_number string where a
        # real UUID property_id was expected.
        result = router.execute(employee="re_agent", tool_name="get_property", message="x", property_id="G-0701")
        assert result["success"] is False
        assert result["error"] == "execution_error"
        assert "uuid" in result["message"].lower()

        # The session must still be usable for a real, valid query right
        # after - this would raise psycopg2.errors.InFailedSqlTransaction
        # before the rollback fix.
        recovered = router.execute(employee="re_agent", tool_name="get_property", message="x", property_id=unit.id)
        assert recovered["result"]["success"] is True
        assert recovered["result"]["property"]["unit_number"] == "G-0701"
