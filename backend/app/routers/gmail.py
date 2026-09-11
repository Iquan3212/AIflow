"""
Gmail connection endpoints. Same shape as app/routers/integrations.py's
Google Calendar flow, on its own prefix and its own OAuth callback route:

  GET    /gmail/status            (auth)   -> connected/available/send_mode
  GET    /gmail/connect           (auth)   -> { "url": <google consent url> }
  GET    /gmail/callback          (public) <- Google redirects here with ?code&state
  DELETE /gmail                   (auth)   -> disconnect
  PATCH  /gmail/mode              (auth)   -> change send_mode
  GET    /gmail/pending           (auth)   -> list pending-approval sends
  POST   /gmail/pending/{id}/approve (auth) -> really send it now
  POST   /gmail/pending/{id}/reject  (auth) -> discard it, never sent
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_agency, get_current_user
from app.logging_config import get_logger
from app.services.gmail import gmail_oauth
from app.services.gmail.gmail_service import GmailService

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/gmail", tags=["Gmail"])


def _row(db: Session, agency_id: str) -> "models.GmailCredential | None":
    return db.query(models.GmailCredential).filter(models.GmailCredential.agency_id == agency_id).first()


@router.get("/status", response_model=schemas.GmailStatus)
def gmail_status(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    row = _row(db, agency.id)
    return schemas.GmailStatus(
        available=gmail_oauth.is_gmail_configured(),
        connected=bool(row and row.refresh_token),
        google_email=row.google_email if row else None,
        send_mode=row.send_mode if row else "approval_required",
    )


@router.get("/connect")
def gmail_connect(
    agency: models.Agency = Depends(get_current_agency),
):
    if not gmail_oauth.is_gmail_configured():
        raise HTTPException(
            status_code=400,
            detail="Gmail OAuth is not configured on the server (set GOOGLE_CLIENT_ID/SECRET and GOOGLE_GMAIL_REDIRECT_URI).",
        )
    return {"url": gmail_oauth.build_consent_url(agency.id)}


@router.get("/callback")
def gmail_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    frontend = settings.frontend_url.rstrip("/")
    if error or not code:
        return RedirectResponse(f"{frontend}/settings?gmail=error")

    agency_id = gmail_oauth.read_state(state)
    if not agency_id:
        return RedirectResponse(f"{frontend}/settings?gmail=invalid_state")

    try:
        tokens = gmail_oauth.exchange_code(code)
    except Exception:
        logger.exception("integration.gmail_oauth.code_exchange_failed", extra={"ctx": {
            "event": "integration.gmail_oauth.code_exchange_failed", "agency_id": agency_id,
        }})
        return RedirectResponse(f"{frontend}/settings?gmail=error")

    row = _row(db, agency_id)
    if row is None:
        row = models.GmailCredential(agency_id=agency_id)
        db.add(row)

    row.access_token = tokens.get("access_token")
    # Google only returns refresh_token on the first consent; keep the old one otherwise.
    if tokens.get("refresh_token"):
        row.refresh_token = tokens["refresh_token"]
    row.scopes = tokens.get("scope", gmail_oauth.SCOPES)
    row.token_uri = gmail_oauth.TOKEN_URI
    if tokens.get("expires_in"):
        row.expiry = datetime.now(timezone.utc) + timedelta(seconds=int(tokens["expires_in"]))
    if tokens.get("access_token"):
        row.google_email = gmail_oauth.fetch_connected_email(tokens["access_token"]) or row.google_email
    db.commit()

    logger.info("integration.gmail.connected", extra={"ctx": {"event": "integration.gmail.connected", "agency_id": agency_id}})
    return RedirectResponse(f"{frontend}/settings?gmail=connected")


@router.delete("")
def gmail_disconnect(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    row = _row(db, agency.id)
    if row:
        db.delete(row)
        db.commit()
        logger.info("integration.gmail.disconnected", extra={"ctx": {"event": "integration.gmail.disconnected", "agency_id": agency.id}})
    return {"message": "Gmail disconnected."}


@router.patch("/mode", response_model=schemas.GmailStatus)
def gmail_set_mode(
    payload: schemas.GmailModeUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    row = _row(db, agency.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Gmail is not connected for this agency.")
    row.send_mode = payload.send_mode
    db.commit()
    logger.info("integration.gmail.mode_changed", extra={"ctx": {
        "event": "integration.gmail.mode_changed", "agency_id": agency.id, "send_mode": payload.send_mode,
    }})
    return schemas.GmailStatus(
        available=gmail_oauth.is_gmail_configured(), connected=bool(row.refresh_token),
        google_email=row.google_email, send_mode=row.send_mode,
    )


@router.get("/pending", response_model=list[schemas.GmailPendingActionOut])
def gmail_list_pending(
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected|sent|failed)$"),
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return GmailService(db).list_pending(agency, status=status)


@router.post("/pending/{pending_id}/approve", response_model=dict)
def gmail_approve_pending(
    pending_id: str,
    agency: models.Agency = Depends(get_current_agency),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = GmailService(db).approve(agency, pending_id, decided_by_user_id=user.id)
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Pending action not found.")
    if result.get("error") == "already_decided":
        raise HTTPException(status_code=409, detail=f"This action was already {result['status']}.")
    return result


@router.post("/pending/{pending_id}/reject", response_model=dict)
def gmail_reject_pending(
    pending_id: str,
    agency: models.Agency = Depends(get_current_agency),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = GmailService(db).reject(agency, pending_id, decided_by_user_id=user.id)
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Pending action not found.")
    if result.get("error") == "already_decided":
        raise HTTPException(status_code=409, detail=f"This action was already {result['status']}.")
    return result
