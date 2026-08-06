"""
Google OAuth 2.0 dance for connecting a business's Google Calendar.

The consent-URL build, code->token exchange, and token refresh are all done with
stdlib urllib so no Google library is required just to connect. The actual
Calendar API calls (in services/calendar/google_calendar.py) use the Google
client library, which is an optional dependency you install when you go live.

State handling: Google's redirect back to us is unauthenticated, so we sign the
connecting business's id into the OAuth `state` param as a short-lived JWT and
verify it on the callback.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import get_settings

settings = get_settings()

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = "https://www.googleapis.com/auth/calendar.events"


def is_google_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri)


def make_state(business_id: str) -> str:
    payload = {
        "business_id": business_id,
        "purpose": "google_calendar_oauth",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def read_state(state: str) -> str | None:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "google_calendar_oauth":
            return None
        return payload.get("business_id")
    except Exception:
        return None


def build_consent_url(business_id: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",     # so we get a refresh_token
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": make_state(business_id),
    }
    return f"{AUTH_URI}?{urllib.parse.urlencode(params)}"


def _post_token(data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        TOKEN_URI, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def exchange_code(code: str) -> dict:
    """Trade an authorization code for access + refresh tokens."""
    return _post_token({
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    })


def refresh_access_token(refresh_token: str) -> dict:
    """Get a fresh access token from a stored refresh token."""
    return _post_token({
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "refresh_token",
    })
