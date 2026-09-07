"""
Picks channels for a notification and sends on each, gated by the
business's own NotificationPreference rows (see ./preferences.py - a
missing row defaults to enabled, so this is opt-out, not opt-in: existing
behavior is unchanged until an owner actually disables something).

notify_customer(): appointment lifecycle events, to the customer's own
contact info. Order of preference: WhatsApp -> SMS -> email, sending on
whichever are both preference-enabled and provider-configured.

notify_owner(): new-lead/support-escalation events, to the business
owner's on-file contact_email. Email only - see preferences.py's module
docstring for why (no stored owner WhatsApp/Instagram contact exists).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from . import preferences
from .base import Notification, NotifyResult
from .email_notifier import EmailNotifier
from .sms_notifier import SmsNotifier
from .whatsapp_notifier import WhatsAppNotifier


class NotificationDispatcher:
    def __init__(self):
        self.email = EmailNotifier()
        self.sms = SmsNotifier()
        self.whatsapp = WhatsAppNotifier()

    def notify_customer(
        self, *, db: Session, business_id: str, event_type: str,
        name: str | None, email: str | None, phone: str | None,
        subject: str, body: str,
    ) -> list[NotifyResult]:
        enabled = {
            channel: preferences.is_enabled(db, business_id, event_type, channel)
            for channel in preferences.CUSTOMER_CHANNELS
        }
        results: list[NotifyResult] = []
        if phone and enabled["whatsapp"] and self.whatsapp.is_configured():
            results.append(self.whatsapp.send(Notification(phone, subject, body)))
        if phone and enabled["sms"] and self.sms.is_configured():
            results.append(self.sms.send(Notification(phone, subject, body)))
        if email and enabled["email"]:
            results.append(self.email.send(Notification(email, subject, body)))
        # Nothing configured/enabled/available? still emit a dev-log email so
        # it's traceable - unless email itself was explicitly disabled.
        if not results and enabled["email"]:
            results.append(self.email.send(Notification(email or "unknown", subject, body)))
        return results

    def notify_owner(
        self, *, db: Session, business, event_type: str, subject: str, body: str,
    ) -> list[NotifyResult]:
        if not preferences.is_enabled(db, business.id, event_type, "email"):
            return []
        contact_email = getattr(business, "contact_email", None)
        if not contact_email:
            return []
        return [self.email.send(Notification(contact_email, subject, body))]
