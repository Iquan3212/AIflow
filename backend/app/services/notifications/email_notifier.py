"""
Email notifier. Uses SMTP if configured, otherwise falls back to logging the
message to stdout so the whole booking + reminder flow is fully exercisable in
local dev with zero external accounts. Plug in Resend/SendGrid SMTP creds (or
swap send() for their HTTP API) to go live.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import get_settings
from app.logging_config import get_logger
from .base import Notification, NotifyResult

settings = get_settings()
logger = get_logger(__name__)


class EmailNotifier:
    channel = "email"

    def is_configured(self) -> bool:
        return bool(settings.smtp_host and settings.smtp_from)

    def send(self, note: Notification) -> NotifyResult:
        if not self.is_configured():
            # Dev/test fallback - SMTP isn't configured, so this log line IS
            # the delivery mechanism (lets a developer verify the booking/
            # reminder flow end-to-end without real SMTP creds). Never
            # reachable in production once SMTP_HOST/SMTP_FROM are set.
            logger.info("notification.dev_logged", extra={"ctx": {
                "event": "notification.dev_logged", "channel": self.channel,
                "to": note.to, "subject": note.subject, "body": note.body,
            }})
            return NotifyResult(True, self.channel, "logged (SMTP not configured)")
        try:
            msg = EmailMessage()
            msg["From"] = settings.smtp_from
            msg["To"] = note.to
            msg["Subject"] = note.subject
            msg.set_content(note.body)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
                if settings.smtp_use_tls:
                    s.starttls()
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
            return NotifyResult(True, self.channel, "sent")
        except Exception as exc:  # never let a notification failure break booking
            logger.exception("integration.email.send_failed", extra={"ctx": {
                "event": "integration.email.send_failed", "channel": self.channel, "to": note.to,
            }})
            return NotifyResult(False, self.channel, str(exc))
