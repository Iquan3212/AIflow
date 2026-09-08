"""
Real trigger integration: proves the actual event sites (LeadService,
LeadTool, AppointmentService, SupportTicketTool) fire the right workflow,
not just that fire_trigger() itself works in isolation (see
test_workflow_engine.py). Against the real dev database; action execution
is mocked (execute_action) so no real Gmail/notification call happens.
Zero LLM tokens.

Run: python3 -m pytest tests/test_workflow_triggers_integration.py -q   (from backend/)
"""

import uuid
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models, schemas
from app.services.lead_service import LeadService
from app.services.scheduling.appointment_service import AppointmentService
from app.services.workflows.actions import ActionOutcome
from app.services.workflows.service import WorkflowService
from app.tools.lead_tool import LeadTool
from app.tools.support_ticket_tool import SupportTicketTool

VALID_ACTIONS = [{"type": "send_notification", "config": {"event_type": "new_lead", "audience": "owner", "subject": "s", "body_template": "b"}}]


@pytest.fixture
def business():
    db = SessionLocal()
    biz = models.Business(name="Trigger Integration Co", slug=f"trigger-int-{uuid.uuid4().hex[:10]}", contact_email="owner@triggerint.example")
    db.add(biz)
    db.commit()
    db.refresh(biz)
    try:
        yield db, biz
    finally:
        wf_ids = [w.id for w in db.query(models.Workflow).filter(models.Workflow.business_id == biz.id).all()]
        for wid in wf_ids:
            db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wid).delete()
        db.query(models.Workflow).filter(models.Workflow.business_id == biz.id).delete()
        db.query(models.Appointment).filter(models.Appointment.business_id == biz.id).delete()
        db.query(models.SupportTicket).filter(models.SupportTicket.business_id == biz.id).delete()
        db.query(models.Lead).filter(models.Lead.business_id == biz.id).delete()
        db.query(models.Business).filter(models.Business.id == biz.id).delete()
        db.commit()
        db.close()


class TestLeadServiceFiresLeadCreated:
    def test_lead_service_create_fires_the_workflow(self, business):
        db, biz = business
        WorkflowService(db).create(
            business_id=biz.id, name="On lead", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            lead = LeadService(db).create(
                business_id=biz.id,
                payload=schemas.LeadCreate(name="Priya", phone="9999999999", email=None, service_interested="Haircut", budget=None),
            )
        mock_exec.assert_called_once()
        runs = db.query(models.WorkflowRun).filter(models.WorkflowRun.trigger_event_id.like(f"%{lead.id}%")).all()
        assert len(runs) == 1
        assert runs[0].trigger_data["lead"]["name"] == "Priya"

    def test_lead_service_update_does_not_refire(self, business):
        db, biz = business
        WorkflowService(db).create(
            business_id=biz.id, name="On lead", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            lead = LeadService(db).create(business_id=biz.id, payload=schemas.LeadCreate(name="Priya"))
            LeadService(db).update(lead.id, biz.id, payload=schemas.LeadUpdate(status="contacted"))
        assert mock_exec.call_count == 1  # update never fires lead_created again


class TestLeadToolFiresLeadCreated:
    def test_lead_tool_created_true_fires_the_workflow(self, business):
        db, biz = business
        WorkflowService(db).create(
            business_id=biz.id, name="On lead via tool", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.lead_ai_service.chat_completion") as mock_chat, \
             patch("app.services.workflows.engine.execute_action") as mock_exec:
            import json
            mock_chat.return_value.content = json.dumps({
                "buying_intent": True, "name": "Rahul", "phone": None, "email": None,
                "service_interested": "Consulting", "budget": None,
            })
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            result = LeadTool(db).execute(message="I'm interested in consulting", db=db, business=biz)

        assert result["ok"] is True
        mock_exec.assert_called_once()


class TestAppointmentServiceFiresAppointmentEvents:
    def test_book_fires_appointment_created(self, business):
        db, biz = business
        WorkflowService(db).create(
            business_id=biz.id, name="On booking", description=None,
            trigger_type=models.WorkflowTriggerType.appointment_created, conditions=[], actions=VALID_ACTIONS,
        )
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        from app.services.scheduling.datetime_utils import now_utc, to_local
        tomorrow_local = to_local(now_utc(), biz.timezone).replace(hour=11, minute=0, second=0, microsecond=0)
        tomorrow_local = tomorrow_local.replace(day=tomorrow_local.day) + __import__("datetime").timedelta(days=1)
        iso = tomorrow_local.strftime("%Y-%m-%dT%H:%M")

        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            outcome = svc.book(biz, start_local_iso=iso, customer_name="Test Customer", customer_phone="1234567890", customer_email=None)

        assert outcome.ok is True
        mock_exec.assert_called_once()

    def test_cancel_fires_appointment_cancelled_but_double_cancel_does_not_refire(self, business):
        db, biz = business
        WorkflowService(db).create(
            business_id=biz.id, name="On cancel", description=None,
            trigger_type=models.WorkflowTriggerType.appointment_cancelled, conditions=[], actions=VALID_ACTIONS,
        )
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        from app.services.scheduling.datetime_utils import now_utc, to_local
        import datetime as dt
        start_local = (to_local(now_utc(), biz.timezone) + dt.timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        iso = start_local.strftime("%Y-%m-%dT%H:%M")

        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            booked = svc.book(biz, start_local_iso=iso, customer_name="Test", customer_phone="1234567890", customer_email=None)
            svc.cancel(biz, booked.appointment.id)
            svc.cancel(biz, booked.appointment.id)  # already cancelled - early-returns, never re-fires

        # 1 for appointment_created (no matching workflow registered) + 1 for the single real cancel
        assert mock_exec.call_count == 1


class TestSupportTicketToolFiresOnlyForHighPriority:
    def test_high_priority_ticket_fires_support_escalated(self, business):
        db, biz = business
        WorkflowService(db).create(
            business_id=biz.id, name="On escalation", description=None,
            trigger_type=models.WorkflowTriggerType.support_escalated, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            SupportTicketTool(db).execute(message="Everything is broken", db=db, business=biz, priority="high")
        mock_exec.assert_called_once()

    def test_normal_priority_ticket_never_fires(self, business):
        db, biz = business
        WorkflowService(db).create(
            business_id=biz.id, name="On escalation", description=None,
            trigger_type=models.WorkflowTriggerType.support_escalated, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            SupportTicketTool(db).execute(message="Minor question", db=db, business=biz, priority="normal")
        mock_exec.assert_not_called()
