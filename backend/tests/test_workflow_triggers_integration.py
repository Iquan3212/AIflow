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
from app.services.scheduling.tools import ToolDispatcher
from app.tools.lead_tool import LeadTool
from app.tools.support_ticket_tool import SupportTicketTool

VALID_ACTIONS = [{"type": "send_notification", "config": {"event_type": "new_lead", "audience": "owner", "subject": "s", "body_template": "b"}}]


@pytest.fixture
def agency():
    db = SessionLocal()
    biz = models.Agency(name="Trigger Integration Co", slug=f"trigger-int-{uuid.uuid4().hex[:10]}", contact_email="owner@triggerint.example")
    db.add(biz)
    db.commit()
    db.refresh(biz)
    try:
        yield db, biz
    finally:
        wf_ids = [w.id for w in db.query(models.Workflow).filter(models.Workflow.agency_id == biz.id).all()]
        for wid in wf_ids:
            db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wid).delete()
        db.query(models.Workflow).filter(models.Workflow.agency_id == biz.id).delete()
        db.query(models.Appointment).filter(models.Appointment.agency_id == biz.id).delete()
        db.query(models.SupportTicket).filter(models.SupportTicket.agency_id == biz.id).delete()
        db.query(models.Lead).filter(models.Lead.agency_id == biz.id).delete()
        db.query(models.Conversation).filter(models.Conversation.agency_id == biz.id).delete()
        db.query(models.Agency).filter(models.Agency.id == biz.id).delete()
        db.commit()
        db.close()


class TestLeadServiceFiresLeadCreated:
    def test_lead_service_create_fires_the_workflow(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On lead", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            lead = LeadService(db).create(
                agency_id=biz.id,
                payload=schemas.LeadCreate(name="Priya", phone="9999999999", email=None, service_interested="Haircut", budget=None),
            )
        mock_exec.assert_called_once()
        runs = db.query(models.WorkflowRun).filter(models.WorkflowRun.trigger_event_id.like(f"%{lead.id}%")).all()
        assert len(runs) == 1
        assert runs[0].trigger_data["lead"]["name"] == "Priya"

    def test_lead_service_update_does_not_refire(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On lead", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            lead = LeadService(db).create(agency_id=biz.id, payload=schemas.LeadCreate(name="Priya"))
            LeadService(db).update(lead.id, biz.id, payload=schemas.LeadUpdate(status="contacted"))
        assert mock_exec.call_count == 1  # update never fires lead_created again


class TestLeadToolFiresLeadCreated:
    def test_lead_tool_created_true_fires_the_workflow(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On lead via tool", description=None,
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
            result = LeadTool(db).execute(message="I'm interested in consulting", db=db, agency=biz)

        assert result["ok"] is True
        mock_exec.assert_called_once()

    def test_lead_tool_fires_workflow_for_preexisting_empty_conversation_lead(self, agency):
        """Regression: conversation_service._get_or_create_lead always
        creates an empty Lead row up front and passes it in as `lead=`
        on every turn of a real customer conversation, so `target is
        None` is never true for that channel. Before this fix, the
        lead_created workflow (and the 'new lead' owner notification)
        silently never fired for any real buyer inquiry via the website/
        WhatsApp/Instagram widget - only for the dashboard's manual lead
        creation. What matters is the lead becoming identifiable for the
        first time, not the row being freshly inserted."""
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On lead via conversation", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        empty_lead = models.Lead(agency_id=biz.id, status="new")
        db.add(empty_lead)
        db.commit()
        db.refresh(empty_lead)

        with patch("app.services.lead_ai_service.chat_completion") as mock_chat, \
             patch("app.services.workflows.engine.execute_action") as mock_exec:
            import json
            mock_chat.return_value.content = json.dumps({
                "buying_intent": True, "name": "Rahul", "phone": "9845011223", "email": None,
                "service_interested": "3BHK in Whitefield", "budget": "1.4-1.5cr",
            })
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            result = LeadTool(db).execute(
                message="I'm Rahul, looking for a 3BHK in Whitefield, budget 1.4-1.5cr",
                db=db, agency=biz, lead=empty_lead,
            )

        assert result["ok"] is True
        assert result["created"] is False  # the row already existed
        mock_exec.assert_called_once()  # but the workflow still fired

    def test_lead_tool_does_not_refire_on_a_later_update_to_an_already_identified_lead(self, agency):
        """Once a conversation's lead has already been identified, a
        later save_lead_info call that only adds more detail must not
        refire lead_created again."""
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On lead via conversation", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        identified_lead = models.Lead(agency_id=biz.id, status="new", name="Rahul", phone="9845011223")
        db.add(identified_lead)
        db.commit()
        db.refresh(identified_lead)

        with patch("app.services.lead_ai_service.chat_completion") as mock_chat, \
             patch("app.services.workflows.engine.execute_action") as mock_exec:
            import json
            mock_chat.return_value.content = json.dumps({
                "buying_intent": True, "name": None, "phone": None, "email": None,
                "service_interested": "3BHK in Whitefield", "budget": "1.4-1.5cr",
            })
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            result = LeadTool(db).execute(
                message="Budget is 1.4-1.5cr for a 3BHK in Whitefield",
                db=db, agency=biz, lead=identified_lead,
            )

        assert result["ok"] is True
        mock_exec.assert_not_called()


class TestWidgetSaveLeadInfoFiresLeadCreated:
    """This is the ACTUAL code path a real customer message on the
    website/WhatsApp/Instagram widget goes through - app.services.
    scheduling.tools.ToolDispatcher._save_lead_info, not app.tools.
    lead_tool.LeadTool. Before this fix, this handler never called
    NotificationDispatcher.notify_owner() or fire_trigger() at all, so
    every real buyer inquiry through the widget silently skipped both
    the 'new lead' owner notification and every lead_created workflow -
    the primary lead-acquisition channel this whole product exists for."""

    def test_widget_save_lead_info_fires_the_workflow_on_first_identification(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On lead via widget", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        conversation = models.Conversation(agency_id=biz.id, visitor_id="visitor-1", channel="website")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        empty_lead = models.Lead(agency_id=biz.id, conversation_id=conversation.id, status="new")
        db.add(empty_lead)
        db.commit()
        db.refresh(empty_lead)

        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            result_json = ToolDispatcher(db, biz, conversation, empty_lead).run(
                "save_lead_info",
                {"name": "Rahul", "phone": "9845011223", "service_interested": "3BHK in Whitefield"},
            )

        import json
        result = json.loads(result_json)
        assert result["ok"] is True
        mock_exec.assert_called_once()  # the workflow fired on first identification

    def test_widget_save_lead_info_does_not_refire_once_already_identified(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On lead via widget", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS,
        )
        conversation = models.Conversation(agency_id=biz.id, visitor_id="visitor-2", channel="website")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        identified_lead = models.Lead(
            agency_id=biz.id, conversation_id=conversation.id, status="new", name="Rahul", phone="9845011223",
        )
        db.add(identified_lead)
        db.commit()
        db.refresh(identified_lead)

        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            ToolDispatcher(db, biz, conversation, identified_lead).run(
                "save_lead_info", {"budget": "1.4-1.5cr"},
            )

        mock_exec.assert_not_called()


class TestAppointmentServiceFiresAppointmentEvents:
    def test_book_fires_appointment_created(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On booking", description=None,
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

    def test_cancel_fires_appointment_cancelled_but_double_cancel_does_not_refire(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On cancel", description=None,
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
    def test_high_priority_ticket_fires_support_escalated(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On escalation", description=None,
            trigger_type=models.WorkflowTriggerType.support_escalated, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            SupportTicketTool(db).execute(message="Everything is broken", db=db, agency=biz, priority="high")
        mock_exec.assert_called_once()

    def test_normal_priority_ticket_never_fires(self, agency):
        db, biz = agency
        WorkflowService(db).create(
            agency_id=biz.id, name="On escalation", description=None,
            trigger_type=models.WorkflowTriggerType.support_escalated, conditions=[], actions=VALID_ACTIONS,
        )
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            SupportTicketTool(db).execute(message="Minor question", db=db, agency=biz, priority="normal")
        mock_exec.assert_not_called()
