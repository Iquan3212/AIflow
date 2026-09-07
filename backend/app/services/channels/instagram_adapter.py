"""
Instagram Messaging adapter: webhook signature verification, inbound DM
normalization, and outbound sending. Same role as whatsapp_adapter.py -
knows Instagram's JSON shape and nothing about the AI Workforce.

Payload shape (documented, stable Meta Graph API / Messenger Platform
format used for Instagram Messaging):
{
  "object": "instagram",
  "entry": [{
    "id": "<IG business account id>",
    "messaging": [{
      "sender": {"id": "<IGSID of the customer>"},
      "recipient": {"id": "<IG business account id>"},
      "message": {"mid": "<message id>", "text": "..."}
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
    """Identical scheme to WhatsApp's (both are Meta Graph API webhooks) -
    fails closed when unconfigured, same as whatsapp_adapter.verify_signature."""
    if not app_secret:
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def parse_inbound(payload: dict) -> list[NormalizedInboundMessage]:
    """Extracts every real customer text DM from one webhook delivery.
    Echoes of the business's own outbound messages, reactions, and
    non-text attachments arrive on the same webhook shape and are skipped
    here, not treated as errors."""
    results: list[NormalizedInboundMessage] = []
    for entry in payload.get("entry", []):
        recipient_account_id = entry.get("id")
        for event in entry.get("messaging", []):
            message = event.get("message")
            if not message or message.get("is_echo"):
                continue
            text = message.get("text")
            if not text:
                continue  # attachment-only DM - not handled in this phase
            sender_id = event.get("sender", {}).get("id")
            account_id = event.get("recipient", {}).get("id") or recipient_account_id
            if not sender_id or not account_id:
                continue
            results.append(NormalizedInboundMessage(
                external_account_id=account_id,
                external_message_id=message["mid"],
                sender_id=sender_id,
                text=text,
            ))
    return results


def send_text_message(ig_account_id: str, access_token: str, recipient_id: str, text: str) -> bool:
    """Sends a reply DM via the Graph API. Same honesty contract as
    whatsapp_adapter.send_text_message: real success/failure only, never
    fabricated, and never raises out to the webhook handler."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_account_id}/messages"
    body = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
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
        logger.warning("channel.instagram.send_failed", extra={"ctx": {
            "event": "channel.instagram.send_failed", "status_code": exc.code,
        }})
        return False
    except Exception:
        logger.exception("channel.instagram.send_failed", extra={"ctx": {
            "event": "channel.instagram.send_failed",
        }})
        return False
