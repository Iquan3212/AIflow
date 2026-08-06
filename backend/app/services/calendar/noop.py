"""Default calendar: does nothing. Appointments still live in our own DB, which
is the source of truth. Swap in GoogleCalendarSync once OAuth is connected."""

from __future__ import annotations

from .base import CalendarEvent


class NoOpCalendar:
    provider = "none"
    def is_configured(self, business) -> bool: return False
    def create_event(self, business, event: CalendarEvent) -> str | None: return None
    def update_event(self, business, event_id, event) -> None: return None
    def delete_event(self, business, event_id) -> None: return None
