from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_business
from app.models import Business
from app.services.support_ticket_service import SupportTicketService

router = APIRouter(prefix="/support-tickets", tags=["Support Tickets"])


@router.get("/", response_model=list[schemas.SupportTicketOut])
def list_tickets(
    status: str | None = Query(default=None, pattern="^(open|in_progress|resolved|closed)$"),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return SupportTicketService(db).get_all(business.id, status=status)


@router.get("/{ticket_id}", response_model=schemas.SupportTicketOut)
def get_ticket(
    ticket_id: str,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    ticket = SupportTicketService(db).get(ticket_id, business.id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}", response_model=schemas.SupportTicketOut)
def update_ticket(
    ticket_id: str,
    payload: schemas.SupportTicketUpdate,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    ticket = SupportTicketService(db).update(
        ticket_id, business.id, status=payload.status, priority=payload.priority
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.delete("/{ticket_id}")
def delete_ticket(
    ticket_id: str,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    success = SupportTicketService(db).delete(ticket_id, business.id)
    if not success:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"message": "Ticket deleted successfully"}
