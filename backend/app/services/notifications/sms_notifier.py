"""
SMS via Twilio. This is a real integration seam: fill TWILIO_* in .env and
`pip install twilio` to activate. Until then it degrades to a dev log so the
booking flow still runs end-to-end.
"""

from __future__ import annotations

from app.config import get_settings
from .base import Notification, NotifyResult

settings = get_settings()


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
            print(f"[SMS:dev] to={note.to}\n{note.body}\n")
            return NotifyResult(True, self.channel, "logged (Twilio not configured)")
        try:
            from twilio.rest import Client  # imported lazily so it's an optional dep
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            client.messages.create(
                to=note.to, from_=settings.twilio_sms_from, body=note.body
            )
            return NotifyResult(True, self.channel, "sent")
        except Exception as exc:
            print(f"[SMS:error] {exc}")
            return NotifyResult(False, self.channel, str(exc))
