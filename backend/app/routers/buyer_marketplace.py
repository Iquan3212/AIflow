"""
Buyer-authenticated views of the buyer's own marketplace conversion
journey (Phase 9, Steps 16-19; site-visit cancellation added in the
Buyer UI phase) - authenticated via get_current_buyer only, exactly like
every other /buyer/* endpoint. Every query is scoped to the
authenticated buyer's own id; none of them ever accept a buyer_id from
the client for authorization.

  GET    /buyer/inquiries
  GET    /buyer/site-visits
  DELETE /buyer/site-visits/{appointment_id}
  GET    /buyer/bookings
"""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from fastapi import APIRouter, Depends, HTTPException
from app import models, schemas
from app.database import get_db
from app.deps import get_current_buyer
from app.services.marketplace.booking_service import BookingService
from app.services.marketplace.property_service import MarketplacePropertyService
from app.services.scheduling.appointment_service import AppointmentService

router = APIRouter(prefix="/buyer", tags=["buyer-marketplace"])

_TERMINAL_STATUSES = {models.AppointmentStatus.completed, models.AppointmentStatus.no_show}


def _property_out(db: Session, property_row: models.Property | None) -> schemas.MarketplacePropertyOut | None:
    """Unlike marketplace search/detail, this is never gated by CURRENT
    public visibility - these are the buyer's own real, permanent
    inquiry/site-visit/booking records (e.g. a booked property is
    naturally `sold`, which would otherwise fail the marketplace's own
    visibility check). Still only ever the same public-safe fields -
    never agency_id/internal_notes/unit rera_number."""
    if property_row is None:
        return None
    return MarketplacePropertyService(db).to_out(property_row, property_row.project)


@router.get("/inquiries", response_model=list[schemas.InquiryOut])
def list_my_inquiries(
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    leads = (
        db.query(models.Lead)
        .options(joinedload(models.Lead.property).joinedload(models.Property.project).joinedload(models.Project.agency))
        .filter(models.Lead.buyer_id == buyer.id)
        .order_by(models.Lead.created_at.desc())
        .all()
    )
    out = []
    for lead in leads:
        property_out = _property_out(db, lead.property)
        if property_out is None:
            continue  # a lead whose property was later deleted - nothing safe left to show
        out.append(schemas.InquiryOut(
            inquiry_id=lead.id, status=lead.status,
            created_at=lead.created_at, updated_at=lead.updated_at,
            property=property_out,
        ))
    return out


@router.get("/site-visits", response_model=list[schemas.BuyerSiteVisitOut])
def list_my_site_visits(
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    appointments = (
        db.query(models.Appointment)
        .options(joinedload(models.Appointment.property).joinedload(models.Property.project).joinedload(models.Project.agency))
        .filter(models.Appointment.buyer_id == buyer.id)
        .order_by(models.Appointment.scheduled_at.desc())
        .all()
    )
    return [
        schemas.BuyerSiteVisitOut(
            appointment_id=appt.id, status=appt.status.value,
            scheduled_at=appt.scheduled_at, end_at=appt.end_at,
            service=appt.service, created_at=appt.created_at,
            property=_property_out(db, appt.property),
        )
        for appt in appointments
    ]


@router.delete("/site-visits/{appointment_id}", response_model=schemas.BuyerSiteVisitOut)
def cancel_my_site_visit(
    appointment_id: str,
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    """Reuses AppointmentService.cancel() exactly as the agency-side
    cancel path does (same calendar sync, customer notification, and
    `appointment_cancelled` workflow trigger) - only the lookup/ownership
    check here is buyer-specific. No reschedule endpoint exists yet (see
    ROADMAP/report) - rescheduling needs real slot re-validation against
    the agency's business hours/conflicts, a bigger change than this
    phase's scope."""
    appt = (
        db.query(models.Appointment)
        .filter(models.Appointment.id == appointment_id, models.Appointment.buyer_id == buyer.id)
        .first()
    )
    if appt is None:
        raise HTTPException(status_code=404, detail="Site visit not found")
    if appt.status in _TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="This site visit has already happened and can't be cancelled.")

    agency = db.query(models.Agency).filter(models.Agency.id == appt.agency_id).first()
    outcome = AppointmentService(db).cancel(agency, appointment_id)
    if not outcome.ok:
        raise HTTPException(status_code=400, detail=outcome.message)

    db.refresh(appt)
    return schemas.BuyerSiteVisitOut(
        appointment_id=appt.id, status=appt.status.value,
        scheduled_at=appt.scheduled_at, end_at=appt.end_at,
        service=appt.service, created_at=appt.created_at,
        property=_property_out(db, appt.property),
    )


@router.get("/bookings", response_model=list[schemas.BuyerBookingOut])
def list_my_bookings(
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    bookings = BookingService(db).get_for_buyer(buyer.id)
    return [
        schemas.BuyerBookingOut(
            booking_id=b.id, status=b.status.value, agreed_price=b.agreed_price,
            created_at=b.created_at, updated_at=b.updated_at,
            property=_property_out(db, b.property),
        )
        for b in bookings
    ]
