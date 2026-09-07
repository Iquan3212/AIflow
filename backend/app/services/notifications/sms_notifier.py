"""
SMS via Twilio. This is a real integration seam: fill TWILIO_* in .env and
`pip install twilio` to activate. Until then it degrades to a dev log so the
booking flow still runs end-to-end.
"""

from __future__ import annotations

from app.config import get_settings
from app.logging_config import get_logger
from .base import Notification, NotifyResult

settings = get_settings()
logger = get_logger(__name__)


class SmsNotifier:
    channel = "sms"

    def is_configured(self) -> bool:
        return bool(
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_sms_from
        )

    def send(self, note: Notification) -> NotifyResult:
        if not self.is_configured():
            # Dev/test fallback - see email_notifier.py for why this is safe.
            logger.info("notification.dev_logged", extra={"ctx": {
                "event": "notification.dev_logged", "channel": self.channel,
                "to": note.to, "body": note.body,
            }})
            return NotifyResult(True, self.channel, "logged (Twilio not configured)")
        try:
            from twilio.rest import Client  # imported lazily so it's an optional dep
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            client.messages.create(
                to=note.to, from_=settings.twilio_sms_from, body=note.body
            )
            return NotifyResult(True, self.channel, "sent")
        except Exception as exc:
            logger.exception("integration.sms.send_failed", extra={"ctx": {
                "event": "integration.sms.send_failed", "channel": self.channel, "to": note.to,
            }})
            return NotifyResult(False, self.channel, str(exc))
