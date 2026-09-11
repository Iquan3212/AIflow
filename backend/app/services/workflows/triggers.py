"""
Trigger dispatch (Step 5/6): called directly from the REAL, existing
service the moment its action actually succeeds (LeadService.create(),
AppointmentService.book()/reschedule()/cancel(), SupportTicketTool -
see each for the exact call site) - never a separate poller, queue, or
webhook. This is the same "simplest production-safe execution model"
choice this project already made for Knowledge Base ingestion
(FastAPI BackgroundTasks, no queue infra) and Gmail (synchronous calls
against the real Gmail API from inside the same request) - workflow
actions here are the same kind of already-synchronous operation
(a notification send, a Gmail draft/send call), so firing them inline,
right after the real state change commits, needs no new infrastructure.

fire_trigger() is deliberately best-effort and exception-safe: a bug in
one agency's misconfigured workflow, or a transient Gmail/notification
failure, must NEVER prevent the real lead/appointment/ticket from having
already been saved - that already happened before this is ever called.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.logging_config import get_logger
from app.services.workflows.engine import WorkflowEngine

logger = get_logger(__name__)


def fire_trigger(db: Session, agency_id: str, trigger_type: models.WorkflowTriggerType, trigger_data: dict, event_id: str) -> None:
    try:
        workflows = (
            db.query(models.Workflow)
            .filter(
                models.Workflow.agency_id == agency_id,
                models.Workflow.trigger_type == trigger_type,
                models.Workflow.status == models.WorkflowStatus.active,
            )
            .all()
        )
    except Exception:
        logger.exception("workflow.trigger_lookup_failed", extra={"ctx": {
            "event": "workflow.trigger_lookup_failed", "agency_id": agency_id, "trigger_type": trigger_type.value,
        }})
        return

    engine = WorkflowEngine(db)
    for workflow in workflows:
        try:
            engine.run(workflow, trigger_data, trigger_event_id=f"{trigger_type.value}:{event_id}:{workflow.id}")
        except Exception:
            db.rollback()
            logger.exception("workflow.run_failed_unexpectedly", extra={"ctx": {
                "event": "workflow.run_failed_unexpectedly", "workflow_id": workflow.id, "agency_id": agency_id,
            }})


# ---- structured trigger_data builders (Step 6) --------------------------
# Every field here is real, already-persisted data - never inferred,
# never fabricated. Conditions/actions only ever read from this shape.

def lead_created_data(lead: models.Lead) -> dict:
    return {
        "lead": {
            "id": lead.id,
            "name": lead.name,
            "phone": lead.phone,
            "email": lead.email,
            "service_interested": lead.service_interested,
            "budget": lead.budget,
            "status": lead.status,
        }
    }


def appointment_data(appt: models.Appointment) -> dict:
    return {
        "appointment": {
            "id": appt.id,
            "customer_name": appt.customer_name,
            "customer_phone": appt.customer_phone,
            "customer_email": appt.customer_email,
            "service": appt.service,
            "scheduled_at": appt.scheduled_at.isoformat() if appt.scheduled_at else None,
            "status": appt.status.value if hasattr(appt.status, "value") else appt.status,
            "source": appt.source,
        }
    }


def support_escalated_data(ticket: models.SupportTicket) -> dict:
    return {
        "support": {
            "id": ticket.id,
            "issue_summary": ticket.issue_summary,
            "priority": ticket.priority,
            "status": ticket.status,
        }
    }
