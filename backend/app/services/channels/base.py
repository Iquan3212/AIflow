"""Shared types/helpers used by both the WhatsApp and Instagram adapters,
so the webhook routers only ever deal with one normalized shape regardless
of which channel it came from - the two adapters differ only in how they
parse Meta's two different JSON payloads and how they call Meta's two
slightly different send-message endpoints, not in any AI/agency logic."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class NormalizedInboundMessage:
    """One inbound customer message, however it arrived."""

    external_account_id: str  # WhatsApp phone_number_id / IG agency account id that received it
    external_message_id: str  # Meta's own message id - the idempotency key
    sender_id: str  # customer's WhatsApp number / IG-scoped sender id - this channel's "visitor_id"
    text: str


def claim_webhook_event(db: Session, channel: str, external_message_id: str, agency_id: str | None) -> bool:
    """Records that this exact message is being processed now. Returns True
    the first time (caller should process it), False if it's a redelivery
    of a message already claimed (caller should skip processing and still
    return 200 to Meta - a duplicate is not an error).

    Meta retries a webhook delivery on anything but a fast 2xx response, so
    the same inbound message can genuinely arrive more than once; this is
    the idempotency guarantee required for that. Implemented as an insert
    racing a unique constraint (channel, external_message_id) rather than a
    check-then-insert, so it's safe even if two deliveries of the same
    event are being handled concurrently."""
    event = models.ChannelWebhookEvent(
        channel=channel, external_message_id=external_message_id, agency_id=agency_id,
    )
    db.add(event)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        logger.info("channel.webhook_duplicate", extra={"ctx": {
            "event": "channel.webhook_duplicate", "channel": channel,
        }})
        return False
