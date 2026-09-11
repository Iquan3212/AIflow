"""Return the calendar adapter for an agency. Google if it's connected (needs
the request DB session to read stored tokens), else the no-op adapter."""

from __future__ import annotations

from .base import CalendarSync
from .noop import NoOpCalendar
from .google_calendar import GoogleCalendarSync


def get_calendar_for(agency, db=None) -> CalendarSync:
    google = GoogleCalendarSync(db)
    if google.is_configured(agency):
        return google
    return NoOpCalendar()
