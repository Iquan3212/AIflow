"""
Buyer-authenticated, read-only views of the buyer's own marketplace
conversion journey (Phase 9, Steps 16-19) - authenticated via
get_current_buyer only, exactly like every other /buyer/* endpoint.
Every query is scoped to the authenticated buyer's own id; none of them
ever accept a buyer_id from the client for authorization.

  GET /buyer/inquiries
  GET /buyer/site-visits
  GET /buyer/bookings
"""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from fastapi import APIRouter, Depends
from app import models, schemas
from app.database import get_db
from app.deps import get_current_buyer
from app.services.marketplace.booking_service import BookingService
from app.services.marketplace.property_service import MarketplacePropertyService

router = APIRouter(prefix="/buyer", tags=["buyer-marketplace"])


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
