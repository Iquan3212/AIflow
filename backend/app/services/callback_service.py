"""
CURRENT CALLBACK MODEL (see ARCHITECTURE.md for the full writeup):

    Buyer requests callback
        -> AIFlow creates a CallbackRequest
        -> Agency is notified (in-app + email, see notification_service.py)
        -> Human agency staff contacts the buyer, using the phone number
           on the request, entirely OUTSIDE this application.

AIFlow never places a phone call itself, and never claims one happened.
There is no telephony/voice integration anywhere in this codebase - see
app/services/scheduling/tools.py's `_request_callback` (the buyer-facing
AI Assistant's real tool) and app/services/prompt_builder.py for where
the buyer-facing AI's own honesty rules about callbacks/calls live. A
future AI voice-calling phase, if ever built, would be a distinct,
separate capability - not implied or promised by anything here.

This is a new domain entity (CallbackRequest, app/models.py) because
nothing equivalent already existed - AIActionApproval represents an AI
*proposing an AIFlow-executed action* (send an email, confirm a visit);
a callback is the opposite shape, a request for a HUMAN to act entirely
outside AIFlow, so it doesn't fit that model and isn't forced into it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.services import notification_service


class CallbackValidationError(ValueError):
    pass


class CallbackNotFoundError(ValueError):
    pass


class InvalidCallbackTransitionError(ValueError):
    pass


_ALLOWED_TRANSITIONS: dict[models.CallbackStatus, frozenset[models.CallbackStatus]] = {
    models.CallbackStatus.requested: frozenset({models.CallbackStatus.assigned, models.CallbackStatus.contacted, models.CallbackStatus.cancelled}),
    models.CallbackStatus.assigned: frozenset({models.CallbackStatus.contacted, models.CallbackStatus.completed, models.CallbackStatus.cancelled}),
    models.CallbackStatus.contacted: frozenset({models.CallbackStatus.completed, models.CallbackStatus.cancelled}),
    models.CallbackStatus.completed: frozenset(),
    models.CallbackStatus.cancelled: frozenset(),
}


def create(
    db: Session,
    agency: models.Agency,
    *,
    lead: models.Lead,
    phone_number: str,
    buyer_id: str | None = None,
    property_id: str | None = None,
    preferred_time: str | None = None,
    notes: str | None = None,
) -> models.CallbackRequest:
    """Validates every relationship against the agency before creating -
    never trusted from the caller:
    - `lead` must already be this exact agency's own Lead (caller's
      responsibility to look it up via LeadService.get(id, agency.id)
      first - never accepted here as a bare id).
    - `property_id`, if supplied, must belong to this same agency.
    - `phone_number` must be non-empty (a callback with no number to
      call is meaningless) - the caller (the AI tool) is responsible for
      capturing it first (from the lead's own phone, or asking the
      buyer) rather than this service inventing or defaulting one.
    """
    if not phone_number or not phone_number.strip():
        raise CallbackValidationError("A phone number is required to request a callback.")

    if property_id:
        prop = (
            db.query(models.Property)
            .filter(models.Property.id == property_id, models.Property.agency_id == agency.id)
            .first()
        )
        if prop is None:
            raise CallbackValidationError("That property does not belong to this agency.")

    if preferred_time is not None and len(preferred_time) > 255:
        raise CallbackValidationError("Preferred time is too long.")
    if notes is not None and len(notes) > 4000:
        raise CallbackValidationError("Notes are too long.")

    callback = models.CallbackRequest(
        agency_id=agency.id,
        buyer_id=buyer_id,
        lead_id=lead.id,
        property_id=property_id,
        phone_number=phone_number.strip(),
        preferred_time=preferred_time,
        notes=notes,
        status=models.CallbackStatus.requested,
    )
    db.add(callback)
    db.commit()
    db.refresh(callback)

    _notify_agency(db, agency, callback, lead)

    return callback


def _notify_agency(db: Session, agency: models.Agency, callback: models.CallbackRequest, lead: models.Lead) -> None:
    from app.services.notifications import preferences as notif_prefs

    who = lead.name or lead.phone or lead.email or "A buyer"
    when = f" Preferred time: {callback.preferred_time}." if callback.preferred_time else ""
    notification_service.create_for_agency(
        db, agency,
        type=models.NotificationType.callback_requested,
        title="Callback requested",
        message=f"{who} requested a callback ({callback.phone_number}).{when}",
        event_id=str(callback.id),
        lead_id=lead.id,
        callback_request_id=callback.id,
        email_event_type=notif_prefs.CALLBACK_REQUESTED,
    )


def get(db: Session, agency_id: str, callback_id: str) -> models.CallbackRequest | None:
    return (
        db.query(models.CallbackRequest)
        .filter(models.CallbackRequest.id == callback_id, models.CallbackRequest.agency_id == agency_id)
        .first()
    )


def list_for_agency(db: Session, agency_id: str, *, lead_id: str | None = None) -> list[models.CallbackRequest]:
    query = db.query(models.CallbackRequest).filter(models.CallbackRequest.agency_id == agency_id)
    if lead_id:
        query = query.filter(models.CallbackRequest.lead_id == lead_id)
    return query.order_by(models.CallbackRequest.requested_at.desc()).all()


def _transition(db: Session, agency_id: str, callback_id: str, new_status: models.CallbackStatus, **timestamp_fields) -> models.CallbackRequest:
    callback = get(db, agency_id, callback_id)
    if callback is None:
        raise CallbackNotFoundError(f"No callback request {callback_id} for this agency.")
    if new_status not in _ALLOWED_TRANSITIONS.get(callback.status, frozenset()):
        raise InvalidCallbackTransitionError(f"Cannot move a callback from {callback.status.value} to {new_status.value}.")

    callback.status = new_status
    for field, value in timestamp_fields.items():
        setattr(callback, field, value)
    db.commit()
    db.refresh(callback)
    return callback


def assign(db: Session, agency_id: str, callback_id: str, *, assigned_to_user_id: str) -> models.CallbackRequest:
    return _transition(
        db, agency_id, callback_id, models.CallbackStatus.assigned,
        assigned_to=assigned_to_user_id, assigned_at=datetime.utcnow(),
    )


def mark_contacted(db: Session, agency_id: str, callback_id: str) -> models.CallbackRequest:
    return _transition(db, agency_id, callback_id, models.CallbackStatus.contacted, contacted_at=datetime.utcnow())


def complete(db: Session, agency_id: str, callback_id: str) -> models.CallbackRequest:
    return _transition(db, agency_id, callback_id, models.CallbackStatus.completed, completed_at=datetime.utcnow())


def cancel(db: Session, agency_id: str, callback_id: str) -> models.CallbackRequest:
    return _transition(db, agency_id, callback_id, models.CallbackStatus.cancelled)
