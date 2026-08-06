"""
Picks channels for a notification and sends on each. Order of preference:
WhatsApp -> SMS -> email, sending on whichever are configured (email always is,
via its dev-log fallback, so a confirmation is never silently dropped).
"""

from __future__ import annotations

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
        self, *, name: str | None, email: str | None, phone: str | None,
        subject: str, body: str,
    ) -> list[NotifyResult]:
        results: list[NotifyResult] = []
        if phone and self.whatsapp.is_configured():
            results.append(self.whatsapp.send(Notification(phone, subject, body)))
        if phone and self.sms.is_configured():
            results.append(self.sms.send(Notification(phone, subject, body)))
        if email:
            results.append(self.email.send(Notification(email, subject, body)))
        # Nothing configured/available? still emit a dev-log email so it's traceable.
        if not results:
            results.append(self.email.send(Notification(email or "unknown", subject, body)))
        return results
