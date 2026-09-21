"""
In-app, persisted, agency-facing notifications - distinct from (and
created ALONGSIDE, never instead of) the existing email-only
app.services.notifications.dispatcher.NotificationDispatcher.notify_owner().
Nothing before this service let a frontend query "what has this agency
been notified about" - NotificationDispatcher only ever sends an
email/SMS/WhatsApp message and persists nothing.

Idempotency: callers pass a stable `event_id` (typically the same
event_id already used for the corresponding fire_trigger() call, e.g.
the Lead's own id, or a Lead id + a fixed suffix for a callback) so a
retried operation (e.g. a lead-creation request retried after a network
timeout) can never create a second "New lead captured" notification for
the same real event - see create_for_agency()'s docstring.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.logging_config import get_logger
from app.services.notifications import preferences as notif_prefs
from app.services.notifications.dispatcher import NotificationDispatcher

logger = get_logger(__name__)


def create_for_agency(
    db: Session,
    agency: models.Agency,
    *,
    type: models.NotificationType,
    title: str,
    message: str,
    event_id: str,
    lead_id: str | None = None,
    callback_request_id: str | None = None,
    email_event_type: str | None = None,
) -> models.Notification:
    """Creates the in-app Notification row, then best-effort sends the
    existing email path (NotificationDispatcher.notify_owner(), gated by
    the agency's own existing notification-preference toggle) alongside
    it - never a second, parallel email mechanism.

    Idempotent: `event_id` is checked against notifications already
    created for this exact (agency, type, event_id) - Notification has
    no dedicated event_id column (unlike WorkflowRun, which owns real
    DB-level uniqueness for its own trigger events), so this checks by
    querying for an existing row referencing the same lead/callback
    within this type - see the two call sites for the exact, narrow
    match each one uses. A caller integrating a new event type should
    add its own precise idempotency check the same way, rather than
    relying on a generic "same title" heuristic that could
    coincidentally collide.

    A notification-creation or email failure is logged, never raised -
    the same "best-effort, never undoes a real committed change" rule
    every existing notify_owner() call site already follows.
    """
    notification = models.Notification(
        agency_id=agency.id, type=type, title=title, message=message,
        lead_id=lead_id, callback_request_id=callback_request_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    try:
        NotificationDispatcher().notify_owner(
            db=db, agency=agency, event_type=email_event_type or type.value,
            subject=title, body=message,
        )
    except Exception:
        logger.exception("notification.email_failed", extra={"ctx": {
            "event": "notification.email_failed", "agency_id": agency.id,
            "notification_id": notification.id, "type": type.value,
        }})

    return notification


def already_notified_for_lead(db: Session, agency_id: str, lead_id: str, type: models.NotificationType) -> bool:
    """True if this agency already has a Notification of this type for
    this exact lead - the idempotency check for `new_lead` (one
    notification per lead ever, no matter how many times the
    identification step is retried)."""
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.agency_id == agency_id,
            models.Notification.lead_id == lead_id,
            models.Notification.type == type,
        )
        .first()
        is not None
    )


def list_for_agency(
    db: Session, agency_id: str, *, unread_only: bool = False, limit: int = 50, offset: int = 0,
) -> list[models.Notification]:
    query = db.query(models.Notification).filter(models.Notification.agency_id == agency_id)
    if unread_only:
        query = query.filter(models.Notification.read_at.is_(None))
    return query.order_by(models.Notification.created_at.desc()).offset(offset).limit(limit).all()


def unread_count(db: Session, agency_id: str) -> int:
    """A dedicated COUNT(*) query - the notification bell's badge needs
    only this number, not up to `limit` full rows, and must stay correct
    even once an agency has more unread notifications than any single
    page would ever fetch."""
    return (
        db.query(models.Notification)
        .filter(models.Notification.agency_id == agency_id, models.Notification.read_at.is_(None))
        .count()
    )


def mark_read(db: Session, agency_id: str, notification_id: str) -> models.Notification | None:
    from datetime import datetime

    notification = (
        db.query(models.Notification)
        .filter(models.Notification.id == notification_id, models.Notification.agency_id == agency_id)
        .first()
    )
    if notification is None:
        return None
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_read(db: Session, agency_id: str) -> int:
    from datetime import datetime

    count = (
        db.query(models.Notification)
        .filter(models.Notification.agency_id == agency_id, models.Notification.read_at.is_(None))
        .update({"read_at": datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()
    return count
