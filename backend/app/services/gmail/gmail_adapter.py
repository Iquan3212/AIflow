"""
Real Gmail API calls. Reads the OAuth tokens stored by the connect flow
(gmail_oauth.py + app/routers/gmail.py) and talks to the Gmail API - this
is the ONLY file in the app that imports googleapiclient/knows Gmail's
request/response shapes. GmailTool (app/tools/gmail_tool.py) calls this
adapter and only ever sees plain dicts/strings back, exactly like every
other tool - Gmail's specifics never leak into Manager/Planner/employees.

is_configured() only touches the DB, so answering "is Gmail connected?" is
cheap and needs no Google library. The actual API calls lazily import
google-api-python-client / google-auth (optional deps, same as Calendar)
and raise GmailNotAvailableError if those aren't installed - our own DB
stays the source of truth regardless, and callers get an honest error
instead of a fabricated result.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from app import models
from app.logging_config import get_logger
from app.services.gmail import gmail_oauth

logger = get_logger(__name__)


class GmailNotAvailableError(Exception):
    """Gmail isn't usable right now - not connected, not configured, or the
    optional google-api-python-client dependency isn't installed. Distinct
    from a real Gmail API error so callers (GmailTool) can tell "we never
    even reached Google" from "Google rejected the request"."""


class GmailAdapter:
    def __init__(self, db):
        self.db = db

    # ---- credential access --------------------------------------------------

    def _row(self, business) -> "models.GmailCredential | None":
        return (
            self.db.query(models.GmailCredential)
            .filter(models.GmailCredential.business_id == business.id)
            .first()
        )

    def is_configured(self, business) -> bool:
        if not gmail_oauth.is_gmail_configured():
            return False
        row = self._row(business)
        return bool(row and row.refresh_token)

    def send_mode(self, business) -> str:
        row = self._row(business)
        return row.send_mode if row else "approval_required"

    def _credentials(self, business):
        """Build a google Credentials object, refreshing the access token if
        it has expired. Raises GmailNotAvailableError rather than returning
        None, so a caller can never mistake "not available" for "empty
        result" (e.g. an empty search)."""
        row = self._row(business)
        if not row or not row.refresh_token:
            raise GmailNotAvailableError("Gmail is not connected for this business.")
        try:
            from google.oauth2.credentials import Credentials  # optional dep
        except ImportError:
            logger.warning("integration.gmail.not_installed", extra={"ctx": {"event": "integration.gmail.not_installed"}})
            raise GmailNotAvailableError("google-auth is not installed on the server.")

        expired = (row.expiry is None) or (row.expiry <= datetime.now(timezone.utc))
        if expired:
            try:
                fresh = gmail_oauth.refresh_access_token(row.refresh_token)
                row.access_token = fresh.get("access_token", row.access_token)
                if fresh.get("expires_in"):
                    row.expiry = datetime.now(timezone.utc) + timedelta(seconds=int(fresh["expires_in"]))
                self.db.commit()
            except Exception:
                logger.exception("integration.gmail.refresh_failed", extra={"ctx": {
                    "event": "integration.gmail.refresh_failed", "business_id": business.id,
                }})
                raise GmailNotAvailableError("Could not refresh the stored Gmail access token.")

        return Credentials(
            token=row.access_token,
            refresh_token=row.refresh_token,
            token_uri=row.token_uri,
            client_id=gmail_oauth.settings.google_client_id,
            client_secret=gmail_oauth.settings.google_client_secret,
            scopes=(row.scopes or gmail_oauth.SCOPES).split(),
        )

    def _service(self, business):
        try:
            from googleapiclient.discovery import build  # optional dep
        except ImportError:
            logger.warning("integration.gmail.not_installed", extra={"ctx": {"event": "integration.gmail.not_installed"}})
            raise GmailNotAvailableError("google-api-python-client is not installed on the server.")
        creds = self._credentials(business)
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    # ---- message parsing ------------------------------------------------

    @staticmethod
    def _header(headers: list[dict], name: str) -> str | None:
        for h in headers or []:
            if h.get("name", "").lower() == name.lower():
                return h.get("value")
        return None

    @classmethod
    def _extract_body_text(cls, payload: dict) -> str:
        """Gmail's payload is a MIME tree, not a flat body - walk it for the
        first text/plain part, falling back to text/html stripped of tags,
        so callers always get plain readable text."""
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return cls._decode_b64(payload["body"]["data"])
        for part in payload.get("parts") or []:
            text = cls._extract_body_text(part)
            if text:
                return text
        if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
            import re
            html = cls._decode_b64(payload["body"]["data"])
            return re.sub(r"<[^>]+>", " ", html)
        return ""

    @staticmethod
    def _decode_b64(data: str) -> str:
        padded = data.replace("-", "+").replace("_", "/")
        padded += "=" * (-len(padded) % 4)
        try:
            return base64.b64decode(padded).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _summarize_message(self, msg: dict) -> dict:
        headers = msg.get("payload", {}).get("headers", [])
        return {
            "id": msg.get("id"),
            "thread_id": msg.get("threadId"),
            "from": self._header(headers, "From"),
            "to": self._header(headers, "To"),
            "subject": self._header(headers, "Subject"),
            "date": self._header(headers, "Date"),
            "snippet": msg.get("snippet"),
        }

    # ---- actions ----------------------------------------------------------

    def search(self, business, query: str, max_results: int = 10) -> list[dict]:
        service = self._service(business)
        resp = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        results = []
        for ref in resp.get("messages", []):
            msg = service.users().messages().get(userId="me", id=ref["id"], format="metadata",
                                                   metadataHeaders=["From", "To", "Subject", "Date"]).execute()
            results.append(self._summarize_message(msg))
        return results

    def read(self, business, message_id: str) -> dict:
        service = self._service(business)
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        summary = self._summarize_message(msg)
        summary["body"] = self._extract_body_text(msg.get("payload", {}))
        return summary

    def create_draft(self, business, to: str, subject: str, body: str) -> dict:
        service = self._service(business)
        mime = MIMEText(body)
        mime["to"] = to
        mime["subject"] = subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
        return {"draft_id": draft.get("id"), "message_id": draft.get("message", {}).get("id")}

    def send(self, business, to: str, subject: str, body: str) -> dict:
        service = self._service(business)
        mime = MIMEText(body)
        mime["to"] = to
        mime["subject"] = subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"message_id": sent.get("id"), "thread_id": sent.get("threadId")}
