"""
WhatsApp Cloud API adapter: webhook signature verification, inbound
payload normalization, and outbound sending. This file knows the shape of
Meta's WhatsApp JSON and nothing about the AI Workforce - routers/
whatsapp.py wires this to the shared, channel-agnostic
conversation_service.process_message_for_agency().

Payload shape (documented, stable Meta Cloud API format):
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "<WABA id>",
    "changes": [{
      "value": {
        "metadata": {"phone_number_id": "...", "display_phone_number": "..."},
        "messages": [{"id": "wamid...", "from": "<customer wa number>",
                       "type": "text", "text": {"body": "..."}}]
      },
      "field": "messages"
    }]
  }]
}
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request

from app.logging_config import get_logger
from app.services.channels.base import NormalizedInboundMessage

logger = get_logger(__name__)

GRAPH_API_VERSION = "v20.0"


def verify_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Validates X-Hub-Signature-256. Without a configured app secret, this
    is skipped and requests are rejected outright (fail closed, not open):
    an unconfigured WHATSAPP_APP_SECRET means the integration isn't
    activated yet, not that verification should be waived."""
    if not app_secret:
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def parse_inbound(payload: dict) -> list[NormalizedInboundMessage]:
    """Extracts every real customer text message from one webhook delivery.
    A single delivery can (rarely) batch more than one message, and
    delivery-status callbacks (sent/delivered/read receipts) and non-text
    message types arrive on the same webhook with no "messages" key or a
    type this app doesn't handle yet - both are silently skipped here,
    not errors."""
    results: list[NormalizedInboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            if not phone_number_id:
                continue
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue  # media/location/etc. - not handled in this phase
                text = (msg.get("text") or {}).get("body")
                if not text:
                    continue
                results.append(NormalizedInboundMessage(
                    external_account_id=phone_number_id,
                    external_message_id=msg["id"],
                    sender_id=msg["from"],
                    text=text,
                ))
    return results


def send_text_message(phone_number_id: str, access_token: str, to: str, text: str) -> bool:
    """Sends a reply back to the customer via the Cloud API. Returns True on
    a real, verified success from Meta - False on any failure (auth,
    network, invalid number, etc.), logged with the diagnostic detail but
    never raised, since a failed outbound send must not break webhook
    processing (Meta still needs its 200 ack) or crash the whole request.
    Never fabricates success - this function does not run at all, and this
    module returns False on every call, until a real access_token is
    configured."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return True
    except urllib.error.HTTPError as exc:
        logger.warning("channel.whatsapp.send_failed", extra={"ctx": {
            "event": "channel.whatsapp.send_failed", "status_code": exc.code,
        }})
        return False
    except Exception:
        logger.exception("channel.whatsapp.send_failed", extra={"ctx": {
            "event": "channel.whatsapp.send_failed",
        }})
        return False
