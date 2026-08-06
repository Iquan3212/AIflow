"""
Calendar sync interface. The appointment service calls create_event /
update_event / delete_event and stores the returned provider event id on the
appointment. Providers (Google/Outlook/Apple) implement this behind the same
shape, so the booking logic never knows which calendar is in use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class CalendarEvent:
    summary: str
    description: str
    start_utc: datetime
    end_utc: datetime
    attendee_email: str | None = None


class CalendarSync(Protocol):
    provider: str
    def is_configured(self, business) -> bool: ...
    def create_event(self, business, event: CalendarEvent) -> str | None: ...
    def update_event(self, business, event_id: str, event: CalendarEvent) -> None: ...
    def delete_event(self, business, event_id: str) -> None: ...
