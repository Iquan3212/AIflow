"""
Agency-only Booking endpoints (Phase 9) - all authenticated via
get_current_agency, exactly like every other agency CRUD router. A
buyer never creates or mutates a Booking; the buyer's own read-only view
lives at GET /buyer/bookings (app/routers/buyer_marketplace.py).

  GET  /bookings              list this agency's bookings (filterable)
  POST /bookings              create a booking
  GET  /bookings/{id}         one booking's detail
  PUT  /bookings/{id}/status  the only path that changes status
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency
from app.services.marketplace.booking_service import (
    AppointmentNotFoundError,
    BookingNotFoundError,
    BookingService,
    BuyerNotFoundError,
    DuplicateActiveBookingError,
    InconsistentRelationshipError,
    InvalidBookingStatusValueError,
    InvalidBookingTransitionError,
    LeadNotFoundError,
    PropertyNotBookableError,
    PropertyNotFoundError,
)
from app.services.inventory.status import InvalidStatusTransitionError

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _to_out(booking: models.Booking) -> schemas.BookingOut:
    return schemas.BookingOut(
        id=booking.id,
        agency_id=booking.agency_id,
        property_id=booking.property_id,
        buyer_id=booking.buyer_id,
        lead_id=booking.lead_id,
        appointment_id=booking.appointment_id,
        status=booking.status.value,
        agreed_price=booking.agreed_price,
        notes=booking.notes,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        property=schemas.LeadPropertySummaryOut.model_validate(booking.property) if booking.property else None,
    )


@router.get("", response_model=list[schemas.BookingOut])
def list_bookings(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    property_id: str | None = Query(default=None),
    buyer_id: str | None = Query(default=None),
    lead_id: str | None = Query(default=None),
):
    try:
        bookings = BookingService(db).get_all(
            agency.id, status=status, property_id=property_id, buyer_id=buyer_id, lead_id=lead_id,
        )
    except InvalidBookingStatusValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return [_to_out(b) for b in bookings]


@router.post("", response_model=schemas.BookingOut, status_code=201)
def create_booking(
    payload: schemas.BookingCreate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        booking = BookingService(db).create(agency.id, payload)
    except PropertyNotFoundError:
        raise HTTPException(status_code=404, detail="Property not found for this agency")
    except (BuyerNotFoundError, LeadNotFoundError, AppointmentNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InconsistentRelationshipError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PropertyNotBookableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except DuplicateActiveBookingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_out(booking)


@router.get("/{booking_id}", response_model=schemas.BookingOut)
def get_booking(
    booking_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    booking = BookingService(db).get(booking_id, agency.id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _to_out(booking)


@router.put("/{booking_id}/status", response_model=schemas.BookingOut)
def update_booking_status(
    booking_id: str,
    payload: schemas.BookingStatusUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        booking = BookingService(db).update_status(booking_id, agency.id, payload.status)
    except BookingNotFoundError:
        raise HTTPException(status_code=404, detail="Booking not found")
    except InvalidBookingStatusValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except InvalidBookingTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_out(booking)
