"""
Notification preferences: which (event, channel) combinations a business
wants enabled. This module is the single source of truth for the canonical
event/channel lists - the model (app.models.NotificationPreference), the
API (app.routers.notifications), and every trigger site (appointment
lifecycle, lead capture, support escalation) all import from here rather
than hardcoding event/channel strings independently.

Two audiences, two channel sets:
- Customer events (appointment lifecycle) go to the customer's own contact
  info via NotificationDispatcher.notify_customer() - email/SMS/WhatsApp,
  matching the fallback chain that already exists there.
- Owner events (new lead, support escalation) go to the business owner via
  NotificationDispatcher.notify_owner() - email only for now, since that's
  the only channel with a real, stored "reach the owner" address
  (Business.contact_email). WhatsApp/Instagram-to-owner would need an
  owner contact field that doesn't exist yet - not fabricated here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models

NEW_LEAD = "new_lead"
APPOINTMENT_CONFIRMED = "appointment_confirmed"
APPOINTMENT_REMINDER = "appointment_reminder"
APPOINTMENT_CANCELLED = "appointment_cancelled"
APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
SUPPORT_ESCALATION = "support_escalation"

CUSTOMER_EVENTS = frozenset({
    APPOINTMENT_CONFIRMED, APPOINTMENT_REMINDER, APPOINTMENT_CANCELLED, APPOINTMENT_RESCHEDULED,
})
OWNER_EVENTS = frozenset({NEW_LEAD, SUPPORT_ESCALATION})
ALL_EVENTS = CUSTOMER_EVENTS | OWNER_EVENTS

CUSTOMER_CHANNELS = ("email", "sms", "whatsapp")
OWNER_CHANNELS = ("email",)

EVENT_LABELS = {
    NEW_LEAD: "New lead captured",
    APPOINTMENT_CONFIRMED: "Appointment confirmed",
    APPOINTMENT_REMINDER: "Appointment reminder",
    APPOINTMENT_CANCELLED: "Appointment cancelled",
    APPOINTMENT_RESCHEDULED: "Appointment rescheduled",
    SUPPORT_ESCALATION: "Support ticket escalated",
}


def channels_for_event(event_type: str) -> tuple[str, ...]:
    return OWNER_CHANNELS if event_type in OWNER_EVENTS else CUSTOMER_CHANNELS


def get_preference_matrix(db: Session, business_id: str) -> list[dict]:
    """Every valid (event, channel) pair for this business, with `enabled`
    resolved against any stored override - missing rows default to True,
    so a business that has never touched this page sees (and gets) exactly
    today's always-on behavior."""
    overrides = {
        (row.event_type, row.channel): row.enabled
        for row in db.query(models.NotificationPreference).filter(
            models.NotificationPreference.business_id == business_id
        )
    }
    matrix = []
    for event_type in sorted(ALL_EVENTS):
        for channel in channels_for_event(event_type):
            matrix.append({
                "event_type": event_type,
                "event_label": EVENT_LABELS[event_type],
                "channel": channel,
                "enabled": overrides.get((event_type, channel), True),
            })
    return matrix


def is_enabled(db: Session, business_id: str, event_type: str, channel: str) -> bool:
    if channel not in channels_for_event(event_type):
        return False
    row = (
        db.query(models.NotificationPreference)
        .filter(
            models.NotificationPreference.business_id == business_id,
            models.NotificationPreference.event_type == event_type,
            models.NotificationPreference.channel == channel,
        )
        .first()
    )
    return row.enabled if row is not None else True


def set_preferences(db: Session, business_id: str, updates: list[dict]) -> list[dict]:
    """Upserts each {event_type, channel, enabled} entry. Validates against
    the canonical lists above - an unknown event/channel or a channel not
    valid for that event raises ValueError rather than silently creating a
    row nothing will ever read (e.g. whatsapp for a support_escalation)."""
    for update in updates:
        event_type, channel = update["event_type"], update["channel"]
        if event_type not in ALL_EVENTS:
            raise ValueError(f"unknown event_type: {event_type!r}")
        if channel not in channels_for_event(event_type):
            raise ValueError(f"channel {channel!r} is not valid for event {event_type!r}")

        row = (
            db.query(models.NotificationPreference)
            .filter(
                models.NotificationPreference.business_id == business_id,
                models.NotificationPreference.event_type == event_type,
                models.NotificationPreference.channel == channel,
            )
            .first()
        )
        if row is None:
            row = models.NotificationPreference(
                business_id=business_id, event_type=event_type, channel=channel,
            )
            db.add(row)
        row.enabled = bool(update["enabled"])

    db.commit()
    return get_preference_matrix(db, business_id)
