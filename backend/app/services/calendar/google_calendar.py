"""
Google Calendar sync. Reads the OAuth tokens stored by the connect flow
(services/calendar/google_oauth.py + routers/integrations.py) and mirrors
appointments into the agency's primary Google Calendar.

is_configured() only touches the DB, so answering "is calendar connected?" is
cheap and needs no Google library. The actual API calls lazily import
google-api-python-client / google-auth (optional deps) and degrade to no-ops if
those aren't installed — our own DB stays the source of truth regardless.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app import models
from app.logging_config import get_logger
from app.services.calendar import google_oauth
from .base import CalendarEvent

logger = get_logger(__name__)


class GoogleCalendarSync:
    provider = "google"

    def __init__(self, db=None):
        self.db = db

    # ---- credential access --------------------------------------------------

    def _row(self, agency) -> "models.CalendarCredential | None":
        if self.db is None:
            return None
        return (
            self.db.query(models.CalendarCredential)
            .filter(
                models.CalendarCredential.agency_id == agency.id,
                models.CalendarCredential.provider == "google",
            )
            .first()
        )

    def is_configured(self, agency) -> bool:
        if not google_oauth.is_google_configured():
            return False
        row = self._row(agency)
        return bool(row and row.refresh_token)

    def _credentials(self, agency):
        """Build a google Credentials object, refreshing the access token if it
        has expired. Returns None if creds are missing or google-auth isn't
        installed."""
        row = self._row(agency)
        if not row or not row.refresh_token:
            return None
        try:
            from google.oauth2.credentials import Credentials  # optional dep
        except ImportError:
            logger.warning("integration.google_calendar.not_installed", extra={"ctx": {"event": "integration.google_calendar.not_installed"}})
            return None

        # Refresh if the stored access token is missing or expired.
        expired = (row.expiry is None) or (row.expiry <= datetime.now(timezone.utc))
        if expired:
            try:
                fresh = google_oauth.refresh_access_token(row.refresh_token)
                row.access_token = fresh.get("access_token", row.access_token)
                if fresh.get("expires_in"):
                    from datetime import timedelta
                    row.expiry = datetime.now(timezone.utc) + timedelta(seconds=int(fresh["expires_in"]))
                self.db.commit()
            except Exception:
                logger.exception("integration.google_calendar.refresh_failed", extra={"ctx": {
                    "event": "integration.google_calendar.refresh_failed", "agency_id": agency.id,
                }})
                return None

        return Credentials(
            token=row.access_token,
            refresh_token=row.refresh_token,
            token_uri=row.token_uri,
            client_id=google_oauth.settings.google_client_id,
            client_secret=google_oauth.settings.google_client_secret,
            scopes=(row.scopes or google_oauth.SCOPES).split(),
        )

    def _service(self, agency):
        from googleapiclient.discovery import build  # optional dep
        creds = self._credentials(agency)
        if creds is None:
            return None
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    # ---- event operations ---------------------------------------------------

    def _body(self, event: CalendarEvent) -> dict:
        body = {
            "summary": event.summary,
            "description": event.description,
            "start": {"dateTime": event.start_utc.astimezone(timezone.utc).isoformat()},
            "end": {"dateTime": event.end_utc.astimezone(timezone.utc).isoformat()},
        }
        if event.attendee_email:
            body["attendees"] = [{"email": event.attendee_email}]
        return body

    def create_event(self, agency, event: CalendarEvent) -> str | None:
        if not self.is_configured(agency):
            return None
        service = self._service(agency)
        if service is None:
            return None
        created = service.events().insert(calendarId="primary", body=self._body(event)).execute()
        return created.get("id")

    def update_event(self, agency, event_id: str, event: CalendarEvent) -> None:
        if not self.is_configured(agency):
            return
        service = self._service(agency)
        if service is None:
            return
        service.events().update(calendarId="primary", eventId=event_id, body=self._body(event)).execute()

    def delete_event(self, agency, event_id: str) -> None:
        if not self.is_configured(agency):
            return
        service = self._service(agency)
        if service is None:
            return
        try:
            service.events().delete(calendarId="primary", eventId=event_id).execute()
        except Exception:
            logger.exception("integration.google_calendar.delete_failed", extra={"ctx": {
                "event": "integration.google_calendar.delete_failed", "agency_id": agency.id,
            }})
