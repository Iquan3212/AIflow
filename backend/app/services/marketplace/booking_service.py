"""
The commercial conversion of a property/unit (Phase 9) - a distinct
business concept from Appointment (a site visit is a meeting; a Booking
is a unit going off the market), never a relabeling of it.

Integrates with, and never fights, Property's EXISTING validated status
lifecycle (app/services/inventory/status.py) - this module calls that
lifecycle's pure `validate_status_transition()` directly (never
PropertyService.update_status(), which auto-commits on its own and
would break this module's own atomicity - see create()/update_status()
below) rather than inventing a second property-status system.

Booking creation/status changes are AGENCY-ONLY (get_current_agency) -
a Buyer never creates or mutates a Booking; buyers only ever get
read-only access to their own bookings (services/marketplace's
GET /buyer/bookings). This is the concrete implementation of "connect
the buyer marketplace to the agency CRM without exposing the CRM to the
buyer" for the booking domain specifically.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.services.inventory.status import validate_status_transition
from app.services.inventory.status import InvalidStatusTransitionError as InvalidPropertyTransitionError
from app.services.marketplace import lead_lifecycle
from app.services.workflows.triggers import booking_data, fire_trigger

ALLOWED_BOOKING_TRANSITIONS: dict[models.BookingStatus, frozenset[models.BookingStatus]] = {
    models.BookingStatus.initiated: frozenset({models.BookingStatus.pending, models.BookingStatus.cancelled}),
    models.BookingStatus.pending: frozenset({models.BookingStatus.confirmed, models.BookingStatus.cancelled}),
    models.BookingStatus.confirmed: frozenset({models.BookingStatus.completed, models.BookingStatus.cancelled}),
    models.BookingStatus.completed: frozenset(),
    models.BookingStatus.cancelled: frozenset(),
}

# Non-cancelled statuses that count as "this property already has an
# active booking" - Step 12/31: checked explicitly against real Booking
# rows, never inferred solely from Property.status (a same-status
# transition would otherwise be a silent no-op, not a guard).
_BLOCKING_BOOKING_STATUSES = frozenset({
    models.BookingStatus.initiated, models.BookingStatus.pending,
    models.BookingStatus.confirmed, models.BookingStatus.completed,
})


class BookingNotFoundError(ValueError):
    pass


class PropertyNotFoundError(ValueError):
    """Raised when property_id doesn't exist, or doesn't belong to the
    acting agency - deliberately the same error either way (Step 15),
    so a cross-agency probe learns nothing about whether the id exists."""


class BuyerNotFoundError(ValueError):
    pass


class LeadNotFoundError(ValueError):
    """Raised when lead_id doesn't exist, or doesn't belong to the
    acting agency."""


class AppointmentNotFoundError(ValueError):
    """Raised when appointment_id doesn't exist, or doesn't belong to
    the acting agency."""


class InconsistentRelationshipError(ValueError):
    """Raised when the supplied buyer/lead/appointment/property
    combination doesn't actually agree with each other (Step 15) - e.g.
    a lead that belongs to a different property, or an appointment that
    belongs to a different buyer. Never silently attach unrelated
    records."""


class PropertyNotBookableError(ValueError):
    pass


class DuplicateActiveBookingError(ValueError):
    pass


class InvalidBookingStatusValueError(ValueError):
    pass


class InvalidBookingTransitionError(ValueError):
    def __init__(self, current: models.BookingStatus, requested: models.BookingStatus):
        self.current = current
        self.requested = requested
        super().__init__(f"Cannot change booking status from '{current.value}' to '{requested.value}'.")


def validate_booking_transition(current: models.BookingStatus, requested: models.BookingStatus) -> None:
    if current == requested:
        return
    if requested not in ALLOWED_BOOKING_TRANSITIONS.get(current, frozenset()):
        raise InvalidBookingTransitionError(current, requested)


class BookingService:
    def __init__(self, db: Session):
        self.db = db

    # ---- reads --------------------------------------------------------

    def get(self, booking_id: str, agency_id: UUID) -> models.Booking | None:
        return (
            self.db.query(models.Booking)
            .options(joinedload(models.Booking.property).joinedload(models.Property.project))
            .filter(models.Booking.id == booking_id, models.Booking.agency_id == agency_id)
            .first()
        )

    def get_all(
        self, agency_id: UUID, *, status: str | None = None,
        property_id: str | None = None, buyer_id: str | None = None, lead_id: str | None = None,
    ) -> list[models.Booking]:
        query = (
            self.db.query(models.Booking)
            .options(joinedload(models.Booking.property).joinedload(models.Property.project))
            .filter(models.Booking.agency_id == agency_id)
        )
        if status:
            try:
                query = query.filter(models.Booking.status == models.BookingStatus(status))
            except ValueError:
                raise InvalidBookingStatusValueError(f"Unknown status: {status!r}")
        if property_id:
            query = query.filter(models.Booking.property_id == property_id)
        if buyer_id:
            query = query.filter(models.Booking.buyer_id == buyer_id)
        if lead_id:
            query = query.filter(models.Booking.lead_id == lead_id)
        return query.order_by(models.Booking.created_at.desc()).all()

    def get_for_buyer(self, buyer_id: UUID) -> list[models.Booking]:
        """Buyer-scoped read - GET /buyer/bookings. Filters ONLY by
        buyer_id, never accepting one from the caller (Step 16/19) -
        the authenticated buyer's own id is the only one ever passed
        in by the router."""
        return (
            self.db.query(models.Booking)
            .options(joinedload(models.Booking.property).joinedload(models.Property.project).joinedload(models.Project.agency))
            .filter(models.Booking.buyer_id == buyer_id)
            .order_by(models.Booking.created_at.desc())
            .all()
        )

    # ---- helpers --------------------------------------------------------

    def _has_active_booking(self, property_id, agency_id: UUID, *, exclude_booking_id: str | None = None) -> bool:
        query = self.db.query(models.Booking).filter(
            models.Booking.property_id == property_id,
            models.Booking.agency_id == agency_id,
            models.Booking.status.in_(_BLOCKING_BOOKING_STATUSES),
        )
        if exclude_booking_id:
            query = query.filter(models.Booking.id != exclude_booking_id)
        return query.first() is not None

    # ---- writes --------------------------------------------------------

    def create(self, agency_id: UUID, payload: schemas.BookingCreate) -> models.Booking:
        """Step 13/15/31: every relationship is re-validated against the
        agency and against each other, never trusted from the client;
        the property row is locked (SELECT ... FOR UPDATE) for the
        whole transaction so two concurrent requests can never both
        create an active booking for the same property - the second
        request blocks until the first commits, then sees its real
        result and is correctly rejected by _has_active_booking. The
        Booking insert and the Property active->reserved transition are
        committed together, ONE transaction - never PropertyService's
        own auto-committing update_status(), which would leave a window
        where the property is reserved but the booking never landed."""
        property_row = (
            self.db.query(models.Property)
            .filter(models.Property.id == payload.property_id, models.Property.agency_id == agency_id)
            .with_for_update()
            .first()
        )
        if property_row is None:
            raise PropertyNotFoundError(f"No property {payload.property_id} for this agency.")

        buyer = None
        if payload.buyer_id:
            buyer = self.db.query(models.Buyer).filter(models.Buyer.id == payload.buyer_id).first()
            if buyer is None:
                raise BuyerNotFoundError(f"No buyer {payload.buyer_id}.")

        lead = None
        if payload.lead_id:
            lead = (
                self.db.query(models.Lead)
                .filter(models.Lead.id == payload.lead_id, models.Lead.agency_id == agency_id)
                .first()
            )
            if lead is None:
                raise LeadNotFoundError(f"No lead {payload.lead_id} for this agency.")
            if lead.property_id and str(lead.property_id) != str(payload.property_id):
                raise InconsistentRelationshipError("This lead is not associated with the given property.")
            if buyer is not None and lead.buyer_id and str(lead.buyer_id) != str(buyer.id):
                raise InconsistentRelationshipError("This lead does not belong to the given buyer.")
            # Prefer deriving the buyer from the lead over trusting a
            # redundant separate buyer_id the client also happened to send.
            if buyer is None and lead.buyer_id:
                buyer = self.db.query(models.Buyer).filter(models.Buyer.id == lead.buyer_id).first()

        appointment = None
        if payload.appointment_id:
            appointment = (
                self.db.query(models.Appointment)
                .filter(models.Appointment.id == payload.appointment_id, models.Appointment.agency_id == agency_id)
                .first()
            )
            if appointment is None:
                raise AppointmentNotFoundError(f"No appointment {payload.appointment_id} for this agency.")
            if appointment.property_id and str(appointment.property_id) != str(payload.property_id):
                raise InconsistentRelationshipError("This appointment is not for the given property.")
            if lead is not None and appointment.lead_id and str(appointment.lead_id) != str(lead.id):
                raise InconsistentRelationshipError("This appointment does not belong to the given lead.")
            if buyer is not None and appointment.buyer_id and str(appointment.buyer_id) != str(buyer.id):
                raise InconsistentRelationshipError("This appointment does not belong to the given buyer.")

        if property_row.status != models.PropertyStatus.active:
            raise PropertyNotBookableError(
                f"Property is '{property_row.status.value}', not available to book."
            )
        if self._has_active_booking(payload.property_id, agency_id):
            raise DuplicateActiveBookingError("This property already has an active booking.")

        booking = models.Booking(
            agency_id=agency_id,
            property_id=payload.property_id,
            buyer_id=buyer.id if buyer else None,
            lead_id=lead.id if lead else None,
            appointment_id=appointment.id if appointment else None,
            agreed_price=payload.agreed_price,
            notes=payload.notes,
            status=models.BookingStatus.initiated,
        )
        self.db.add(booking)

        # Property lifecycle side effect: active -> reserved (Step 12) -
        # reuses the exact same validated transition rules the Agency
        # dashboard's own inventory already enforces.
        validate_status_transition(property_row.status, models.PropertyStatus.reserved)
        property_row.status = models.PropertyStatus.reserved

        self.db.commit()
        self.db.refresh(booking)
        fire_trigger(
            self.db, agency_id, models.WorkflowTriggerType.booking_initiated,
            booking_data(booking), event_id=str(booking.id),
        )
        return booking

    def update_status(self, booking_id: str, agency_id: UUID, new_status: str) -> models.Booking:
        booking = (
            self.db.query(models.Booking)
            .filter(models.Booking.id == booking_id, models.Booking.agency_id == agency_id)
            .with_for_update()
            .first()
        )
        if booking is None:
            raise BookingNotFoundError(f"No booking {booking_id} for this agency.")

        try:
            requested = models.BookingStatus(new_status)
        except ValueError:
            raise InvalidBookingStatusValueError(f"Unknown status: {new_status!r}")

        validate_booking_transition(booking.status, requested)
        previous_status = booking.status
        booking.status = requested

        if booking.property_id:
            property_row = (
                self.db.query(models.Property)
                .filter(models.Property.id == booking.property_id, models.Property.agency_id == agency_id)
                .with_for_update()
                .first()
            )
            if property_row is not None:
                if requested == models.BookingStatus.confirmed:
                    # reserved -> sold (Step 12)
                    try:
                        validate_status_transition(property_row.status, models.PropertyStatus.sold)
                        property_row.status = models.PropertyStatus.sold
                    except InvalidPropertyTransitionError:
                        pass  # already sold (e.g. by a race already resolved) - leave as-is, never error the booking confirm over it
                elif requested == models.BookingStatus.cancelled:
                    if previous_status in (models.BookingStatus.initiated, models.BookingStatus.pending):
                        # Only ever a hold, never sold yet - release it.
                        if property_row.status == models.PropertyStatus.reserved:
                            property_row.status = models.PropertyStatus.active
                    # else: previous_status was `confirmed` (property already
                    # `sold`) - Phase 7's `sold` is deliberately one-way
                    # (sold -> archived only); Phase 9 does not fight that.
                    # The property stays `sold` until an agency deliberately
                    # relists it through the existing inventory lifecycle.

        self.db.commit()
        self.db.refresh(booking)

        # Phase 11: booking.initiated (the create()-time transition) is
        # already covered above; confirmed/cancelled/completed are the
        # other three lifecycle stages the spec calls out (there is
        # deliberately no separate trigger for the intermediate
        # "pending" status - not one of the named workflow categories).
        # Event id includes the target status so a genuinely later
        # transition back through the same status (blocked by
        # ALLOWED_BOOKING_TRANSITIONS today, but not something this
        # trigger call should assume) is never conflated with an earlier
        # one at the DB idempotency layer.
        _BOOKING_TRIGGER_BY_STATUS = {
            models.BookingStatus.confirmed: models.WorkflowTriggerType.booking_confirmed,
            models.BookingStatus.cancelled: models.WorkflowTriggerType.booking_cancelled,
            models.BookingStatus.completed: models.WorkflowTriggerType.booking_completed,
        }
        trigger_type = _BOOKING_TRIGGER_BY_STATUS.get(requested)
        if trigger_type is not None:
            fire_trigger(
                self.db, agency_id, trigger_type,
                booking_data(booking), event_id=f"{booking.id}:{requested.value}",
            )

        # Final Hardening: "only after the existing booking lifecycle
        # reaches the defined successful conversion state" - `completed`
        # is the one real terminal success status (ALLOWED_BOOKING_
        # TRANSITIONS above: only confirmed -> completed, never merely
        # initiated/pending/confirmed, and never from cancelled). Never
        # fires for `confirmed` alone (that's "sold", not yet "done") or
        # for `cancelled` (booking_service.py's own cancel path above
        # never reaches this branch since requested != completed there).
        if requested == models.BookingStatus.completed and booking.lead_id:
            lead = self.db.query(models.Lead).filter(models.Lead.id == booking.lead_id, models.Lead.agency_id == agency_id).first()
            if lead is not None:
                lead_lifecycle.system_advance(
                    self.db, lead, agency_id, "converted",
                    caused_by=f"booking {booking.id} reached completed",
                )
        return booking
