"""
CRUD for an agency's WhatsApp/Instagram connection (ChannelCredential),
analogous to the CalendarCredential helpers in services/calendar/. Also
where an inbound webhook resolves WHICH agency a message belongs to:
Meta's payload identifies the receiving phone number/IG account, not the
agency directly, so `get_agency_for_external_account` is the tenant-
resolution step every webhook handler starts with.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models

VALID_CHANNELS = ("whatsapp", "instagram")


class ExternalAccountAlreadyConnected(Exception):
    """Raised when the phone_number_id/IG account id being connected is
    already claimed by a different agency - the uq_channel_credentials_
    external_account constraint's application-level surface."""


def get_credential(db: Session, agency_id: str, channel: str) -> models.ChannelCredential | None:
    return (
        db.query(models.ChannelCredential)
        .filter(
            models.ChannelCredential.agency_id == agency_id,
            models.ChannelCredential.channel == channel,
        )
        .first()
    )


def list_credentials(db: Session, agency_id: str) -> list[models.ChannelCredential]:
    return (
        db.query(models.ChannelCredential)
        .filter(models.ChannelCredential.agency_id == agency_id)
        .all()
    )


def get_agency_for_external_account(db: Session, channel: str, external_account_id: str) -> models.Agency | None:
    """Tenant resolution for an inbound webhook: given the phone_number_id
    (WhatsApp) or IG agency account id (Instagram) the message arrived
    at, find which agency owns that connection. Only ever matches a
    credential with status="connected" - a disconnected/stale row must not
    let messages route to an agency that no longer has this number."""
    credential = (
        db.query(models.ChannelCredential)
        .filter(
            models.ChannelCredential.channel == channel,
            models.ChannelCredential.external_account_id == external_account_id,
            models.ChannelCredential.status == "connected",
        )
        .first()
    )
    return credential.agency if credential else None


def get_connected_credential(db: Session, channel: str, external_account_id: str) -> models.ChannelCredential | None:
    return (
        db.query(models.ChannelCredential)
        .filter(
            models.ChannelCredential.channel == channel,
            models.ChannelCredential.external_account_id == external_account_id,
            models.ChannelCredential.status == "connected",
        )
        .first()
    )


def upsert_credential(
    db: Session,
    agency_id: str,
    channel: str,
    external_account_id: str,
    access_token: str,
    display_name: str | None = None,
) -> models.ChannelCredential:
    """Save (or replace) an agency's connection details for one channel.
    Manual entry only, deliberately - a full "Connect with Meta" OAuth
    button needs an app reviewed by Meta Business, which this repository
    does not have; the agency owner instead pastes the phone_number_id/
    IG account id and access token they obtained from their own Meta App
    Dashboard or WhatsApp Business Platform / Instagram Graph API setup."""
    credential = get_credential(db, agency_id, channel)
    if credential is None:
        credential = models.ChannelCredential(agency_id=agency_id, channel=channel)
        db.add(credential)

    credential.external_account_id = external_account_id
    credential.access_token = access_token
    credential.display_name = display_name
    credential.status = "connected"
    credential.connected_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ExternalAccountAlreadyConnected(
            f"{channel} account {external_account_id!r} is already connected to another agency"
        ) from exc
    db.refresh(credential)
    return credential


def disconnect_credential(db: Session, agency_id: str, channel: str) -> models.ChannelCredential | None:
    credential = get_credential(db, agency_id, channel)
    if credential is None:
        return None
    credential.status = "disconnected"
    credential.access_token = None
    # Release the claim on this external account so it can be reconnected
    # by (or reassigned to) any agency later - the uq_channel_credentials_
    # external_account unique constraint would otherwise treat this row's
    # old value as still occupied forever, even after disconnecting.
    credential.external_account_id = None
    db.commit()
    db.refresh(credential)
    return credential
