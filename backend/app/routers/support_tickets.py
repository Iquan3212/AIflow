from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_agency
from app.models import Agency
from app.services.support_ticket_service import SupportTicketService

router = APIRouter(prefix="/support-tickets", tags=["Support Tickets"])


@router.get("/", response_model=list[schemas.SupportTicketOut])
def list_tickets(
    status: str | None = Query(default=None, pattern="^(open|in_progress|resolved|closed)$"),
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return SupportTicketService(db).get_all(agency.id, status=status)


@router.get("/{ticket_id}", response_model=schemas.SupportTicketOut)
def get_ticket(
    ticket_id: str,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    ticket = SupportTicketService(db).get(ticket_id, agency.id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}", response_model=schemas.SupportTicketOut)
def update_ticket(
    ticket_id: str,
    payload: schemas.SupportTicketUpdate,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    ticket = SupportTicketService(db).update(
        ticket_id, agency.id, status=payload.status, priority=payload.priority
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.delete("/{ticket_id}")
def delete_ticket(
    ticket_id: str,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    success = SupportTicketService(db).delete(ticket_id, agency.id)
    if not success:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"message": "Ticket deleted successfully"}
