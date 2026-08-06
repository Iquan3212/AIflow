"""
WhatsApp via Meta's Cloud API. Real seam: fill WHATSAPP_* in .env to activate.

NOTE (compliance): business-initiated WhatsApp messages outside the 24h customer
service window must use a pre-approved *template*. Appointment reminders are
business-initiated, so `template_name` should point at an approved utility
template. Free-form text only works inside an open 24h window. See ARCHITECTURE.md
on Meta's restrictions before enabling this in production.
"""

from __future__ import annotations

import json
import urllib.request

from app.config import get_settings
from .base import Notification, NotifyResult

settings = get_settings()


class WhatsAppNotifier:
    channel = "whatsapp"

    def is_configured(self) -> bool:
        return bool(settings.whatsapp_phone_id and settings.whatsapp_token)

    def send(self, note: Notification) -> NotifyResult:
        if not self.is_configured():
            print(f"[WHATSAPP:dev] to={note.to}\n{note.body}\n")
            return NotifyResult(True, self.channel, "logged (WhatsApp not configured)")
        try:
            url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "to": note.to,
                "type": "text",
                "text": {"body": note.body},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            return NotifyResult(True, self.channel, "sent")
        except Exception as exc:
            print(f"[WHATSAPP:error] {exc}")
            return NotifyResult(False, self.channel, str(exc))
