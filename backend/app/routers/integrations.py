"""
Calendar integration endpoints (Google Calendar).

Flow:
  GET  /integrations/google/connect   (auth)   -> { "url": <google consent url> }
       frontend redirects the owner to that url
  GET  /integrations/google/callback  (public)  <- Google redirects here with ?code&state
       we verify state, exchange the code, store tokens, then bounce back to the app
  GET  /integrations/google/status    (auth)   -> { "connected": bool }
  DELETE /integrations/google         (auth)   -> disconnect
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_business
from app.services.calendar import google_oauth

settings = get_settings()
router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get("/google/status")
def google_status(
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    row = _get_row(db, business.id)
    return {
        "provider": "google",
        "available": google_oauth.is_google_configured(),
        "connected": bool(row and row.refresh_token),
    }


@router.get("/google/connect")
def google_connect(
    business: models.Business = Depends(get_current_business),
):
    if not google_oauth.is_google_configured():
        raise HTTPException(
            status_code=400,
            detail="Google OAuth is not configured on the server (set GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI).",
        )
    return {"url": google_oauth.build_consent_url(business.id)}


@router.get("/google/callback")
def google_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    frontend = settings.frontend_url.rstrip("/")
    if error or not code:
        return RedirectResponse(f"{frontend}/appointments?calendar=error")

    business_id = google_oauth.read_state(state)
    if not business_id:
        return RedirectResponse(f"{frontend}/appointments?calendar=invalid_state")

    try:
        tokens = google_oauth.exchange_code(code)
    except Exception as exc:
        print(f"[google:callback:error] {exc}")
        return RedirectResponse(f"{frontend}/appointments?calendar=error")

    row = _get_row(db, business_id)
    if row is None:
        row = models.CalendarCredential(business_id=business_id, provider="google")
        db.add(row)

    row.access_token = tokens.get("access_token")
    # Google only returns refresh_token on the first consent; keep the old one otherwise.
    if tokens.get("refresh_token"):
        row.refresh_token = tokens["refresh_token"]
    row.scopes = tokens.get("scope", google_oauth.SCOPES)
    row.token_uri = google_oauth.TOKEN_URI
    if tokens.get("expires_in"):
        row.expiry = datetime.now(timezone.utc) + timedelta(seconds=int(tokens["expires_in"]))
    db.commit()

    return RedirectResponse(f"{frontend}/appointments?calendar=connected")


@router.delete("/google")
def google_disconnect(
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    row = _get_row(db, business.id)
    if row:
        db.delete(row)
        db.commit()
    return {"message": "Google Calendar disconnected."}


def _get_row(db: Session, business_id: str):
    return (
        db.query(models.CalendarCredential)
        .filter(
            models.CalendarCredential.business_id == business_id,
            models.CalendarCredential.provider == "google",
        )
        .first()
    )
