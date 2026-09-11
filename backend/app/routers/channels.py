"""
WhatsApp/Instagram: public Meta webhooks + the authenticated dashboard
endpoints an agency uses to connect/view/disconnect a channel.

Every inbound message, from either channel, is normalized by its adapter
(services/channels/{whatsapp,instagram}_adapter.py) and then handed to the
exact same conversation_service.process_message_for_agency() the
website widget uses - there is no separate WhatsApp/Instagram AI logic.
See ARCHITECTURE.md's "Channels" section for the full data flow.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_agency
from app.logging_config import get_logger
from app.services.channels import credentials
from app.services.channels.base import claim_webhook_event
from app.services.channels import whatsapp_adapter, instagram_adapter
from app.services.shared.conversation_service import process_message_for_agency

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["Channels"])


# =====================================================================
# Dashboard endpoints (authenticated) - connect/view/disconnect a channel
# =====================================================================

@router.get("/channels/", response_model=list[schemas.ChannelCredentialOut])
def list_channels(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    """Every channel the agency could connect, WHATSAPP/Instagram
    included even if never configured - the dashboard needs to show a real
    "not connected" state, not just omit the row."""
    existing = {c.channel: c for c in credentials.list_credentials(db, agency.id)}
    result = []
    for channel in credentials.VALID_CHANNELS:
        row = existing.get(channel)
        if row is not None:
            result.append(row)
        else:
            result.append(models.ChannelCredential(channel=channel, status="disconnected"))
    return result


@router.put("/channels/{channel}", response_model=schemas.ChannelCredentialOut)
def connect_channel(
    channel: str,
    payload: schemas.ChannelCredentialUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    if channel not in credentials.VALID_CHANNELS:
        raise HTTPException(status_code=404, detail="Unknown channel")
    try:
        saved = credentials.upsert_credential(
            db, agency_id=agency.id, channel=channel,
            external_account_id=payload.external_account_id,
            access_token=payload.access_token,
            display_name=payload.display_name,
        )
    except credentials.ExternalAccountAlreadyConnected:
        logger.warning("channel.connect_conflict", extra={"ctx": {"event": "channel.connect_conflict", "channel": channel}})
        raise HTTPException(
            status_code=409,
            detail="This account is already connected to another agency. Disconnect it there first.",
        )
    logger.info("channel.connected", extra={"ctx": {"event": "channel.connected", "channel": channel}})
    return saved


@router.delete("/channels/{channel}", response_model=schemas.ChannelCredentialOut)
def disconnect_channel(
    channel: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    if channel not in credentials.VALID_CHANNELS:
        raise HTTPException(status_code=404, detail="Unknown channel")
    saved = credentials.disconnect_credential(db, agency.id, channel)
    if saved is None:
        raise HTTPException(status_code=404, detail="Channel was never connected")
    logger.info("channel.disconnected", extra={"ctx": {"event": "channel.disconnected", "channel": channel}})
    return saved


# =====================================================================
# WhatsApp webhook (public - Meta calls these, no bearer auth; protected
# by signature verification instead)
# =====================================================================

@router.get("/webhooks/whatsapp")
def whatsapp_verify(request: Request):
    """One-time handshake Meta performs when you save the webhook URL in
    the App Dashboard. Must echo back hub.challenge verbatim, and only if
    hub.verify_token matches WHATSAPP_WEBHOOK_VERIFY_TOKEN."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and settings.whatsapp_webhook_verify_token
        and params.get("hub.verify_token") == settings.whatsapp_webhook_verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    logger.warning("channel.whatsapp.verify_failed", extra={"ctx": {"event": "channel.whatsapp.verify_failed"}})
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    if not whatsapp_adapter.verify_signature(raw_body, signature, settings.whatsapp_app_secret):
        logger.warning("channel.whatsapp.invalid_signature", extra={"ctx": {"event": "channel.whatsapp.invalid_signature"}})
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    for msg in whatsapp_adapter.parse_inbound(payload):
        _handle_inbound(
            db, channel="whatsapp", msg=msg,
            get_agency=lambda acc: credentials.get_agency_for_external_account(db, "whatsapp", acc),
            send=lambda cred, reply: whatsapp_adapter.send_text_message(
                cred.external_account_id, cred.access_token, msg.sender_id, reply,
            ),
        )

    # Meta only cares about a fast 2xx ack, and retries aggressively on
    # anything else - always return 200 here regardless of what happened
    # processing any individual message above (each failure is already
    # logged inside _handle_inbound).
    return {"status": "ok"}


# =====================================================================
# Instagram webhook - same shape, different payload/endpoint via its adapter
# =====================================================================

@router.get("/webhooks/instagram")
def instagram_verify(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and settings.instagram_webhook_verify_token
        and params.get("hub.verify_token") == settings.instagram_webhook_verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    logger.warning("channel.instagram.verify_failed", extra={"ctx": {"event": "channel.instagram.verify_failed"}})
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/instagram")
async def instagram_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    if not instagram_adapter.verify_signature(raw_body, signature, settings.instagram_app_secret):
        logger.warning("channel.instagram.invalid_signature", extra={"ctx": {"event": "channel.instagram.invalid_signature"}})
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    for msg in instagram_adapter.parse_inbound(payload):
        _handle_inbound(
            db, channel="instagram", msg=msg,
            get_agency=lambda acc: credentials.get_agency_for_external_account(db, "instagram", acc),
            send=lambda cred, reply: instagram_adapter.send_text_message(
                cred.external_account_id, cred.access_token, msg.sender_id, reply,
            ),
        )

    return {"status": "ok"}


def _handle_inbound(db: Session, channel: str, msg, get_agency, send) -> None:
    """Shared tail of both webhook handlers: resolve tenant, dedupe, run
    the channel-agnostic core, send the reply. Never raises - every failure
    is caught and logged so one bad message in a batch can't take down the
    rest of the delivery or the 200 ack Meta needs."""
    agency = get_agency(msg.external_account_id)
    if agency is None:
        logger.warning(f"channel.{channel}.unknown_account", extra={"ctx": {
            "event": f"channel.{channel}.unknown_account",
        }})
        return

    if not claim_webhook_event(db, channel, msg.external_message_id, agency.id):
        return  # already processed this exact message - not an error

    try:
        result = process_message_for_agency(
            db, agency=agency, visitor_id=msg.sender_id,
            conversation_id=None, message=msg.text, channel=channel,
        )
    except Exception:
        logger.exception(f"channel.{channel}.processing_failed", extra={"ctx": {
            "event": f"channel.{channel}.processing_failed",
        }})
        return

    credential = credentials.get_connected_credential(db, channel, msg.external_account_id)
    if credential is None or not credential.access_token:
        logger.warning(f"channel.{channel}.no_credential_for_reply", extra={"ctx": {
            "event": f"channel.{channel}.no_credential_for_reply",
        }})
        return

    send(credential, result["reply"])
