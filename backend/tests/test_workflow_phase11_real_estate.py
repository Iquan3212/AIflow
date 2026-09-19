"""
Phase 11: real-estate workflow triggers (lead status/qualification,
site-visit confirm/complete/no-show, booking lifecycle) and the new
run_ai_specialist workflow action - proves the actual event sites fire
the right workflow (mirroring test_workflow_triggers_integration.py's
style for the Phase 5 triggers) and that the AI-workforce action runs
exactly one bounded specialist turn through the real ManagerAgent/
Registry/ToolRouter pipeline, never bypassing AIActionApproval.

Against the real dev database with real throwaway rows, cleaned up
after each test. Only chat_completion is mocked for the AI-specialist
tests (deterministic, scripted responses) - zero real LLM tokens
anywhere in this file.

Run: python3 -m pytest tests/test_workflow_phase11_real_estate.py -q   (from backend/)
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
from app.services.ai_workforce.approval_service import AIActionApprovalService
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.lead_service import LeadService
from app.services.marketplace.booking_service import BookingService
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import now_utc, to_local
from app.services.workflows.actions import ActionOutcome, execute_action
from app.services.workflows.service import WorkflowService, WorkflowValidationError

VALID_ACTIONS = [{"type": "send_notification", "config": {"event_type": "new_lead", "audience": "owner", "subject": "s", "body_template": "b"}}]


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Phase11 WF Test {suffix}",
        slug=f"phase11-wf-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@phase11wftest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_active_property(db, agency, *, unit_number: str = "U-1"):
    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="Phase11 Project", city="Bengaluru"))
    ProjectService(db).update(project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
    unit = PropertyService(db).create(
        agency.id,
        schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=2,
            carpet_area_sqft=Decimal("1000.00"), price=Decimal("8000000.00"), unit_number=unit_number,
        ),
    )
    PropertyService(db).update_status(unit.id, agency.id, "active")
    return project, unit


def _cleanup(db, agency):
    wf_ids = [w.id for w in db.query(models.Workflow).filter(models.Workflow.agency_id == agency.id).all()]
    for wid in wf_ids:
        db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wid).delete()
    db.query(models.Workflow).filter(models.Workflow.agency_id == agency.id).delete()
    db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == agency.id).delete()
    db.query(models.AgentExecution).filter(models.AgentExecution.agency_id == agency.id).delete()
    db.query(models.Booking).filter(models.Booking.agency_id == agency.id).delete()
    db.query(models.Appointment).filter(models.Appointment.agency_id == agency.id).delete()
    db.query(models.Lead).filter(models.Lead.agency_id == agency.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def agency():
    db, biz = _make_agency(uuid.uuid4().hex[:6])
    try:
        yield db, biz
    finally:
        _cleanup(db, biz)


@pytest.fixture
def two_agencies():
    db1, biz1 = _make_agency("x" + uuid.uuid4().hex[:6])
    db2, biz2 = _make_agency("y" + uuid.uuid4().hex[:6])
    try:
        yield (db1, biz1), (db2, biz2)
    finally:
        _cleanup(db1, biz1)
        _cleanup(db2, biz2)


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tool_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _tomorrow_iso(agency, hour=11):
    import datetime as dt
    local = to_local(now_utc(), agency.timezone) + dt.timedelta(days=1)
    while local.weekday() == 6:  # demo business hours are closed Sundays
        local += dt.timedelta(days=1)
    local = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    return local.strftime("%Y-%m-%dT%H:%M")


# =====================================================================
# Lead status / qualification triggers (LeadService.update)
# =====================================================================

class TestLeadStatusChangedTrigger:
    def test_status_change_fires_lead_status_changed(self, agency):
        db, biz = agency
        lead = LeadService(db).create(biz.id, schemas.LeadCreate(name="Priya"))
        WorkflowService(db).create(
            agency_id=biz.id, name="On status change", description=None,
            trigger_type=models.WorkflowTriggerType.lead_status_changed, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            LeadService(db).update(lead.id, biz.id, schemas.LeadUpdate(status="contacted"))
        mock_exec.assert_called_once()

    def test_same_status_is_not_a_change_and_does_not_refire(self, agency):
        db, biz = agency
        lead = LeadService(db).create(biz.id, schemas.LeadCreate(name="Priya", service_interested="x"))
        WorkflowService(db).create(
            agency_id=biz.id, name="On status change", description=None,
            trigger_type=models.WorkflowTriggerType.lead_status_changed, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            # status stays "new" -> "new": a real field update with no
            # actual status change must not fire lead_status_changed.
            LeadService(db).update(lead.id, biz.id, schemas.LeadUpdate(status="new"))
        mock_exec.assert_not_called()

    def test_unrelated_field_update_does_not_fire_status_changed(self, agency):
        db, biz = agency
        lead = LeadService(db).create(biz.id, schemas.LeadCreate(name="Priya"))
        WorkflowService(db).create(
            agency_id=biz.id, name="On status change", description=None,
            trigger_type=models.WorkflowTriggerType.lead_status_changed, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            LeadService(db).update(lead.id, biz.id, schemas.LeadUpdate(budget="2 Cr"))
        mock_exec.assert_not_called()


class TestLeadQualifiedTrigger:
    def test_setting_qualification_score_fires_lead_qualified(self, agency):
        db, biz = agency
        lead = LeadService(db).create(biz.id, schemas.LeadCreate(name="Rahul"))
        WorkflowService(db).create(
            agency_id=biz.id, name="On qualified", description=None,
            trigger_type=models.WorkflowTriggerType.lead_qualified, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            LeadService(db).update(lead.id, biz.id, schemas.LeadUpdate(qualification_score=82, qualification_notes="Strong intent"))
        mock_exec.assert_called_once()

    def test_same_score_again_does_not_refire(self, agency):
        db, biz = agency
        lead = LeadService(db).create(biz.id, schemas.LeadCreate(name="Rahul"))
        WorkflowService(db).create(
            agency_id=biz.id, name="On qualified", description=None,
            trigger_type=models.WorkflowTriggerType.lead_qualified, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            LeadService(db).update(lead.id, biz.id, schemas.LeadUpdate(qualification_score=50))
            LeadService(db).update(lead.id, biz.id, schemas.LeadUpdate(qualification_score=50))
        assert mock_exec.call_count == 1


# =====================================================================
# Site-visit (Appointment) confirm/complete/no-show triggers
# =====================================================================

class TestSiteVisitLifecycleTriggers:
    def _book(self, db, biz):
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            outcome = svc.book(biz, start_local_iso=_tomorrow_iso(biz), customer_name="Test", customer_phone="1234567890", customer_email=None)
        return svc, outcome.appointment

    def test_confirm_fires_appointment_confirmed_but_double_confirm_does_not_refire(self, agency):
        db, biz = agency
        svc, appt = self._book(db, biz)
        WorkflowService(db).create(
            agency_id=biz.id, name="On confirm", description=None,
            trigger_type=models.WorkflowTriggerType.appointment_confirmed, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            svc.confirm(biz, appt.id)
            svc.confirm(biz, appt.id)  # already confirmed - guarded, never re-fires
        assert mock_exec.call_count == 1

    def test_complete_fires_appointment_completed(self, agency):
        db, biz = agency
        svc, appt = self._book(db, biz)
        svc.confirm(biz, appt.id)
        WorkflowService(db).create(
            agency_id=biz.id, name="On complete", description=None,
            trigger_type=models.WorkflowTriggerType.appointment_completed, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            outcome = svc.complete(biz, appt.id)
        assert outcome.ok is True
        mock_exec.assert_called_once()

    def test_no_show_fires_appointment_no_show(self, agency):
        db, biz = agency
        svc, appt = self._book(db, biz)
        svc.confirm(biz, appt.id)
        WorkflowService(db).create(
            agency_id=biz.id, name="On no-show", description=None,
            trigger_type=models.WorkflowTriggerType.appointment_no_show, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            outcome = svc.mark_no_show(biz, appt.id)
        assert outcome.ok is True
        mock_exec.assert_called_once()

    def test_invalid_transition_never_fires(self, agency):
        """completed -> confirmed is not an allowed action transition -
        the real, pre-existing appointment_status.py guard rejects it
        before any trigger could fire."""
        db, biz = agency
        svc, appt = self._book(db, biz)
        svc.confirm(biz, appt.id)
        svc.complete(biz, appt.id)
        WorkflowService(db).create(
            agency_id=biz.id, name="On confirm", description=None,
            trigger_type=models.WorkflowTriggerType.appointment_confirmed, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            outcome = svc.confirm(biz, appt.id)
        assert outcome.ok is False
        mock_exec.assert_not_called()


# =====================================================================
# Booking lifecycle triggers
# =====================================================================

class TestBookingLifecycleTriggers:
    def test_create_fires_booking_initiated(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz)
        WorkflowService(db).create(
            agency_id=biz.id, name="On booking initiated", description=None,
            trigger_type=models.WorkflowTriggerType.booking_initiated, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            booking = BookingService(db).create(biz.id, schemas.BookingCreate(property_id=unit.id))
        mock_exec.assert_called_once()
        runs = db.query(models.WorkflowRun).filter(models.WorkflowRun.trigger_event_id.like(f"%{booking.id}%")).all()
        assert len(runs) == 1
        assert runs[0].trigger_data["booking"]["property_id"] == unit.id

    def test_status_transitions_fire_the_matching_trigger(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz)
        for trig in (
            models.WorkflowTriggerType.booking_confirmed,
            models.WorkflowTriggerType.booking_cancelled,
            models.WorkflowTriggerType.booking_completed,
        ):
            WorkflowService(db).create(
                agency_id=biz.id, name=f"On {trig.value}", description=None,
                trigger_type=trig, conditions=[], actions=VALID_ACTIONS,
            )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            booking = BookingService(db).create(biz.id, schemas.BookingCreate(property_id=unit.id))
            call_count_after_create = mock_exec.call_count
            BookingService(db).update_status(booking.id, biz.id, "pending")  # no trigger registered for "pending"
            assert mock_exec.call_count == call_count_after_create
            BookingService(db).update_status(booking.id, biz.id, "confirmed")
            assert mock_exec.call_count == call_count_after_create + 1
            BookingService(db).update_status(booking.id, biz.id, "completed")
            assert mock_exec.call_count == call_count_after_create + 2

    def test_double_cancel_of_same_status_does_not_refire(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz)
        WorkflowService(db).create(
            agency_id=biz.id, name="On cancel", description=None,
            trigger_type=models.WorkflowTriggerType.booking_cancelled, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            booking = BookingService(db).create(biz.id, schemas.BookingCreate(property_id=unit.id))
            base = mock_exec.call_count
            BookingService(db).update_status(booking.id, biz.id, "cancelled")
            assert mock_exec.call_count == base + 1
            # Same status again is a documented no-op in validate_booking_transition -
            # the DB-level WorkflowRun idempotency key (booking.id:cancelled) absorbs
            # the repeat, so this must never count as a second real trigger fire.
            BookingService(db).update_status(booking.id, biz.id, "cancelled")
            assert mock_exec.call_count == base + 1


# =====================================================================
# New trigger types are validated correctly by the existing generic
# condition-field/action-vocabulary machinery - no new validation code
# needed, but this proves the extension actually took effect.
# =====================================================================

class TestNewTriggerFieldsValidateCorrectly:
    def test_lead_qualified_condition_on_qualification_score_is_accepted(self, agency):
        db, biz = agency
        wf = WorkflowService(db).create(
            agency_id=biz.id, name="High score only", description=None,
            trigger_type=models.WorkflowTriggerType.lead_qualified,
            conditions=[{"field": "lead.qualification_score", "op": "eq", "value": 90}],
            actions=VALID_ACTIONS,
        )
        assert wf.id is not None

    def test_booking_condition_on_unknown_field_is_rejected(self, agency):
        db, biz = agency
        with pytest.raises(WorkflowValidationError):
            WorkflowService(db).create(
                agency_id=biz.id, name="Bad condition", description=None,
                trigger_type=models.WorkflowTriggerType.booking_confirmed,
                conditions=[{"field": "booking.agreed_price", "op": "eq", "value": "1"}],  # not in _BOOKING_FIELDS
                actions=VALID_ACTIONS,
            )

    def test_marketplace_lead_scoped_via_condition_on_lead_created(self, agency):
        """Phase 11 deliberately has no separate 'marketplace_inquiry'
        trigger type - a workflow scopes itself to marketplace-sourced
        leads via a condition on the existing lead_created trigger's
        (now-extended) lead.buyer_id field instead."""
        db, biz = agency
        wf = WorkflowService(db).create(
            agency_id=biz.id, name="Marketplace leads only", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created,
            conditions=[{"field": "lead.buyer_id", "op": "is_set"}],
            actions=VALID_ACTIONS,
        )
        assert wf.id is not None


# =====================================================================
# run_ai_specialist action - bounded, real ManagerAgent/ToolRouter path
# =====================================================================

class TestRunAiSpecialistActionErrors:
    def test_unknown_specialist_fails_cleanly(self, agency):
        db, biz = agency
        outcome = execute_action(
            "run_ai_specialist", db=db, agency=biz, trigger_data={"lead": {"id": "x"}},
            config={"specialist": "not_a_real_specialist", "message_template": "hi"},
        )
        assert outcome.status == "failed"
        assert "Unknown or unsupported specialist" in outcome.error

    def test_manager_is_not_a_valid_specialist_target(self, agency):
        db, biz = agency
        outcome = execute_action(
            "run_ai_specialist", db=db, agency=biz, trigger_data={},
            config={"specialist": "manager", "message_template": "hi"},
        )
        assert outcome.status == "failed"

    def test_missing_message_template_fails_cleanly(self, agency):
        db, biz = agency
        outcome = execute_action(
            "run_ai_specialist", db=db, agency=biz, trigger_data={"lead": {"id": "x"}},
            config={"specialist": "lead_qualifier"},
        )
        assert outcome.status == "failed"
        assert "message_template" in outcome.error

    def test_lead_id_that_does_not_exist_fails_cleanly(self, agency):
        db, biz = agency
        outcome = execute_action(
            "run_ai_specialist", db=db, agency=biz, trigger_data={"lead": {"id": str(uuid.uuid4())}},
            config={"specialist": "lead_qualifier", "message_template": "Qualify this lead."},
        )
        assert outcome.status == "failed"
        assert "No lead" in outcome.error

    def test_no_lead_id_field_runs_without_a_bound_lead(self, agency):
        """Some specialists (e.g. property_matcher on a generic trigger)
        may legitimately run with no specific lead bound - lead_id_field
        resolving to nothing is not itself an error."""
        db, biz = agency
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.return_value = _msg(content="No specific property match without more criteria.")
            outcome = execute_action(
                "run_ai_specialist", db=db, agency=biz, trigger_data={},
                config={"specialist": "property_matcher", "message_template": "Any new matches?"},
            )
        assert outcome.status == "succeeded"
        assert outcome.result["specialist"] == "property_matcher"


class TestRunAiSpecialistRealExecution:
    def test_lead_qualifier_really_updates_the_real_lead_row(self, agency):
        """End-to-end through the real ManagerAgent/Registry/ToolRouter
        pipeline (only chat_completion is mocked) - proves this is one
        bounded specialist turn, not a second AI brain, and that its
        real tool call actually persists (LeadService.update()) exactly
        as a live chat turn would."""
        db, biz = agency
        lead = LeadService(db).create(biz.id, schemas.LeadCreate(name="Priya", budget="1.4 Cr", service_interested="3BHK"))

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="", tool_calls=[_tool_call("update_lead_qualification", {
                    "lead_id": lead.id, "qualification_score": 85, "qualification_notes": "Strong budget signal.",
                })]),
                _msg(content="Qualified with a high score based on real budget/unit-type signals."),
            ]
            outcome = execute_action(
                "run_ai_specialist", db=db, agency=biz,
                trigger_data={"lead": {"id": lead.id, "name": lead.name}},
                config={"specialist": "lead_qualifier", "message_template": "Qualify lead {lead_name}."},
            )

        assert outcome.status == "succeeded"
        assert outcome.result["specialist"] == "lead_qualifier"
        db.refresh(lead)
        assert lead.qualification_score == 85
        assert lead.qualification_notes == "Strong budget signal."

        executions = db.query(models.AgentExecution).filter(
            models.AgentExecution.agency_id == biz.id, models.AgentExecution.employee == "lead_qualifier",
        ).all()
        assert len(executions) == 1
        assert executions[0].lead_id == lead.id

    def test_site_visit_specialist_proposal_creates_a_real_pending_approval_never_auto_executed(self, agency):
        """confirm_visit is proposal-only (see realestate_visit_followup_
        tools.py's module docstring) - the workflow action must complete
        as 'succeeded' (the AI ran its bounded turn) while the actual
        appointment confirmation stays gated behind a real, pending
        AIActionApproval - never bypassed, and never conflated with the
        workflow engine's own ApprovalRequest primitive."""
        db, biz = agency
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        with patch("app.services.workflows.engine.execute_action"):
            booked = svc.book(biz, start_local_iso=_tomorrow_iso(biz), customer_name="Test", customer_phone="1234567890", customer_email=None)
        appt = booked.appointment

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("confirm_visit", {"appointment_id": appt.id})]),
                _msg(content="I've requested confirmation for this site visit - awaiting approval."),
            ]
            outcome = execute_action(
                "run_ai_specialist", db=db, agency=biz,
                trigger_data={"appointment": {"id": appt.id}},
                config={"specialist": "site_visit", "message_template": "Please confirm this site visit.",
                        "lead_id_field": "appointment.lead_id"},
            )

        assert outcome.status == "succeeded"  # the AI turn itself succeeded

        db.refresh(appt)
        assert appt.status == models.AppointmentStatus.scheduled  # never auto-confirmed

        pending = db.query(models.AIActionApproval).filter(
            models.AIActionApproval.agency_id == biz.id,
            models.AIActionApproval.action_type == "confirm_site_visit",
        ).all()
        assert len(pending) == 1
        assert pending[0].status == models.AIActionApprovalStatus.pending

        # Approving it now DOES execute the real, authoritative service -
        # proving this action never pre-empted or duplicated that path.
        approved, execution_result = AIActionApprovalService(db).approve_and_execute(pending[0].id, biz)
        assert execution_result["executed"] is True
        db.refresh(appt)
        assert appt.status == models.AppointmentStatus.confirmed


class TestRunAiSpecialistRequiresApprovalGating:
    def test_requires_approval_pauses_before_the_specialist_ever_runs(self, agency):
        """A workflow author can gate run_ai_specialist behind the
        engine's own generic ApprovalRequest (unrelated to
        AIActionApproval) with zero new gating code - it already works
        for any action type."""
        db, biz = agency
        lead = LeadService(db).create(biz.id, schemas.LeadCreate(name="Gated Lead"))
        wf = WorkflowService(db).create(
            agency_id=biz.id, name="Gated AI qualification", description=None,
            trigger_type=models.WorkflowTriggerType.lead_status_changed, conditions=[],
            actions=[{
                "type": "run_ai_specialist",
                "config": {"specialist": "lead_qualifier", "message_template": "Qualify {lead_name}."},
                "requires_approval": True,
            }],
        )

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            LeadService(db).update(lead.id, biz.id, schemas.LeadUpdate(status="contacted"))
            mock_chat.assert_not_called()  # never ran - still waiting on the human gate

        run = db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wf.id).first()
        assert run.status == models.WorkflowRunStatus.waiting_approval
        approval = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.workflow_step_run_id == run.steps[0].id).first()
        assert approval.status == models.ApprovalRequestStatus.pending

        from app.services.workflows.engine import WorkflowEngine
        approval.status = models.ApprovalRequestStatus.approved
        db.commit()
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Qualified."),
            ]
            WorkflowEngine(db).resume_after_approval(approval, decided_by_user_id=None)
            mock_chat.assert_called()  # now it actually ran, exactly once approved


# =====================================================================
# Tenant isolation for the new trigger types
# =====================================================================

class TestTenantIsolationForNewTriggers:
    def test_booking_confirmed_in_agency_a_never_fires_agency_bs_workflow(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _, unit1 = _make_active_property(db1, biz1)
        WorkflowService(db2).create(
            agency_id=biz2.id, name="B's workflow", description=None,
            trigger_type=models.WorkflowTriggerType.booking_confirmed, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            booking = BookingService(db1).create(biz1.id, schemas.BookingCreate(property_id=unit1.id))
            BookingService(db1).update_status(booking.id, biz1.id, "pending")
            BookingService(db1).update_status(booking.id, biz1.id, "confirmed")
        mock_exec.assert_not_called()

    def test_lead_qualified_in_agency_a_never_fires_agency_bs_workflow(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        lead1 = LeadService(db1).create(biz1.id, schemas.LeadCreate(name="A's lead"))
        WorkflowService(db2).create(
            agency_id=biz2.id, name="B's workflow", description=None,
            trigger_type=models.WorkflowTriggerType.lead_qualified, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            LeadService(db1).update(lead1.id, biz1.id, schemas.LeadUpdate(qualification_score=99))
        mock_exec.assert_not_called()
