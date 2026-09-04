from sqlalchemy.orm import Session

from app.services.support_ticket_service import SupportTicketService


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

        return {"ok": True, "ticket_id": ticket.id, "priority": ticket.priority, "status": ticket.status}
