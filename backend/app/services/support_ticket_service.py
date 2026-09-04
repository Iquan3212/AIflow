from sqlalchemy.orm import Session

from app import models


class SupportTicketService:
    """CRUD over SupportTicket - the persisted output of the Support AI
    Workforce employee."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        business_id: str,
        issue_summary: str,
        priority: str = "normal",
        lead_id: str | None = None,
    ) -> models.SupportTicket:
        ticket = models.SupportTicket(
            business_id=business_id,
            issue_summary=issue_summary,
            priority=priority,
            lead_id=lead_id,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def get_all(self, business_id: str, status: str | None = None) -> list[models.SupportTicket]:
        query = self.db.query(models.SupportTicket).filter(models.SupportTicket.business_id == business_id)
        if status:
            query = query.filter(models.SupportTicket.status == status)
        return query.order_by(models.SupportTicket.created_at.desc()).all()

    def get(self, ticket_id: str, business_id: str) -> models.SupportTicket | None:
        return (
            self.db.query(models.SupportTicket)
            .filter(models.SupportTicket.id == ticket_id, models.SupportTicket.business_id == business_id)
            .first()
        )

    def update(
        self,
        ticket_id: str,
        business_id: str,
        status: str | None = None,
        priority: str | None = None,
    ) -> models.SupportTicket | None:
        ticket = self.get(ticket_id, business_id)
        if ticket is None:
            return None
        if status:
            ticket.status = status
        if priority:
            ticket.priority = priority
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def delete(self, ticket_id: str, business_id: str) -> bool:
        ticket = self.get(ticket_id, business_id)
        if ticket is None:
            return False
        self.db.delete(ticket)
        self.db.commit()
        return True
