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

def lead_data(lead: models.Lead) -> dict:
    """Shared by every lead_* trigger (Phase 5's lead_created, Phase 11's
    lead_status_changed/lead_qualified) - one shape, so a workflow's
    conditions/templates behave identically regardless of which lead
    event fired them. buyer_id/property_id (Phase 11, additive) let a
    workflow scope itself to marketplace-sourced leads only (e.g. a
    condition on `lead.buyer_id` `is_set`) without a separate
    "marketplace_inquiry" trigger type - get_or_create_marketplace_lead()
    already fires lead_created through LeadService.create() exactly like
    every other lead."""
    return {
        "lead": {
            "id": lead.id,
            "name": lead.name,
            "phone": lead.phone,
            "email": lead.email,
            "service_interested": lead.service_interested,
            "budget": lead.budget,
            "status": lead.status,
            "buyer_id": lead.buyer_id,
            "property_id": lead.property_id,
            "qualification_score": lead.qualification_score,
            "qualification_notes": lead.qualification_notes,
        }
    }


# Old name kept as an alias - every existing call site (lead_service.py,
# lead_tool.py, scheduling/tools.py) fires lead_created specifically, and
# this is the exact shape they already relied on, now just extended.
lead_created_data = lead_data


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
            # Phase 11, additive: lets a site-visit workflow reach the
            # associated marketplace buyer/property (e.g. to notify the
            # buyer, or to condition on `appointment.property_id`
            # is_set to scope a workflow to real-estate site visits
            # only, vs. a non-marketplace appointment where both stay
            # null exactly as they always have).
            "buyer_id": appt.buyer_id,
            "property_id": appt.property_id,
            "lead_id": appt.lead_id,
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


def booking_data(booking: models.Booking) -> dict:
    """Phase 11: the commercial-conversion counterpart to appointment_data
    above - see models.py's Booking docstring for why this is a distinct
    business concept from Appointment, never a relabeling of it."""
    return {
        "booking": {
            "id": booking.id,
            "property_id": booking.property_id,
            "buyer_id": booking.buyer_id,
            "lead_id": booking.lead_id,
            "appointment_id": booking.appointment_id,
            "status": booking.status.value if hasattr(booking.status, "value") else booking.status,
            "agreed_price": str(booking.agreed_price) if booking.agreed_price is not None else None,
        }
    }
