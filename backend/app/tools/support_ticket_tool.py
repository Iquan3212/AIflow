from sqlalchemy.orm import Session

from app import models
from app.services.support_ticket_service import SupportTicketService
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.notifications import preferences as notif_prefs
from app.services.workflows.triggers import fire_trigger, support_escalated_data
from app.logging_config import get_logger

logger = get_logger(__name__)


class SupportTicketTool:
    """Persists a real SupportTicket for every issue the Support employee
    handles, mirroring the pattern AIDraft established for Finance/Marketing
    (Phase 6) - no LLM call needed here, the ticket is just a durable record
    of what the customer/owner reported."""

    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        message: str,
        db=None,
        business=None,
        conversation=None,
        lead=None,
        priority: str = "normal",
        **kwargs,
    ) -> dict:
        db = db or self.db
        if business is None:
            return {"ok": False, "error": "missing_business"}

        ticket = SupportTicketService(db).create(
            business_id=business.id,
            issue_summary=message,
            priority=priority,
            lead_id=getattr(lead, "id", None),
        )

        if ticket.priority == "high":
            # Best-effort: a notification failure must never undo or mask a
            # real, already-committed ticket.
            try:
                NotificationDispatcher().notify_owner(
                    db=db, business=business, event_type=notif_prefs.SUPPORT_ESCALATION,
                    subject=f"Support escalation — {business.name}",
                    body=f"A support issue was escalated: {ticket.issue_summary}",
                )
            except Exception:
                logger.exception("notification.support_escalation_failed", extra={"ctx": {
                    "event": "notification.support_escalation_failed", "business_id": business.id, "ticket_id": ticket.id,
                }})

            fire_trigger(
                db, business.id, models.WorkflowTriggerType.support_escalated,
                support_escalated_data(ticket), event_id=str(ticket.id),
            )

        return {"ok": True, "ticket_id": ticket.id, "priority": ticket.priority, "status": ticket.status}
