"""
Google OAuth 2.0 dance for connecting a business's Gmail account. Deliberately
mirrors app/services/calendar/google_oauth.py's shape (same stdlib-urllib
consent-URL/code-exchange/refresh approach, same signed-state pattern) -
Gmail and Calendar are two independent connections a business can make,
each with its own scope and its own callback route, but there is no reason
for the OAuth mechanics themselves to differ.

State handling: Google's redirect back to us is unauthenticated, so we sign
the connecting business's id into the OAuth `state` param as a short-lived
JWT and verify it on the callback - the `purpose` claim ("gmail_oauth")
means a Calendar callback's state can never be replayed against the Gmail
callback or vice versa, even though both use the same JWT secret.

Scopes - minimum practical set for search + read + draft + send:
- gmail.readonly: search and read messages/threads. No write access at all.
- gmail.compose: create/update/delete drafts, and send a draft or a new
  message. This single scope covers both "draft" and "send" - there is no
  narrower official scope that covers drafting without also allowing send,
  and gmail.send alone (send-only) cannot create drafts. Using compose
  instead of the full gmail.modify or mail.google.com scopes avoids
  granting label/thread-management or full-mailbox access this app never
  uses.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose"

_STATE_PURPOSE = "gmail_oauth"


def is_gmail_configured() -> bool:
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_gmail_redirect_uri
    )


def make_state(business_id: str) -> str:
    payload = {
        "business_id": business_id,
        "purpose": _STATE_PURPOSE,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def read_state(state: str) -> str | None:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != _STATE_PURPOSE:
            logger.warning("integration.gmail_oauth.wrong_state_purpose", extra={"ctx": {"event": "integration.gmail_oauth.wrong_state_purpose"}})
            return None
        return payload.get("business_id")
    except Exception:
        logger.warning("integration.gmail_oauth.invalid_state", extra={"ctx": {"event": "integration.gmail_oauth.invalid_state"}})
        return None


def build_consent_url(business_id: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_gmail_redirect_uri,
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
        "redirect_uri": settings.google_gmail_redirect_uri,
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


def fetch_connected_email(access_token: str) -> str | None:
    """Best-effort: which Gmail address did the owner just connect? Purely
    for display in the Settings UI (so an owner can see *which* inbox is
    connected) - never used for authorization decisions, and a failure here
    must never fail the OAuth connection itself."""
    try:
        req = urllib.request.Request(
            USERINFO_URI, headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data.get("email")
    except Exception:
        logger.warning("integration.gmail_oauth.userinfo_failed", extra={"ctx": {"event": "integration.gmail_oauth.userinfo_failed"}})
        return None
