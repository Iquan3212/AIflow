"""
Pure scheduling logic: no database, no framework, no I/O.

Everything here is deterministic and unit-tested (see tests/test_scheduling.py).
The DB layer feeds it plain data (business hours, existing bookings as UTC
intervals) and gets back answers: is this slot bookable, what are the open
slots, does this collide with an existing appointment.

Keeping this layer pure is what makes "no double bookings" a property we can
actually prove, instead of hoping the happy path in a service method holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone

from .datetime_utils import get_tz, now_utc


@dataclass(frozen=True)
class DayHours:
    """Opening hours for a single weekday, in the business's local wall clock."""
    weekday: int          # 0=Mon .. 6=Sun
    is_open: bool
    open_time: time | None
    close_time: time | None


@dataclass(frozen=True)
class Interval:
    """A half-open UTC time interval [start, end)."""
    start: datetime
    end: datetime

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Rules:
    slot_duration_minutes: int = 30
    buffer_minutes: int = 0
    min_notice_minutes: int = 60
    max_advance_days: int = 60


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _expand(interval: Interval, buffer_minutes: int) -> Interval:
    """Grow an existing booking by the buffer on both sides, so back-to-back
    bookings that violate the buffer are treated as conflicts."""
    if buffer_minutes <= 0:
        return interval
    b = timedelta(minutes=buffer_minutes)
    return Interval(interval.start - b, interval.end + b)


def has_conflict(candidate: Interval, existing: list[Interval], buffer_minutes: int = 0) -> bool:
    """True if `candidate` overlaps any existing booking (buffer-expanded)."""
    candidate = Interval(_as_utc(candidate.start), _as_utc(candidate.end))
    for booked in existing:
        booked = Interval(_as_utc(booked.start), _as_utc(booked.end))
        if candidate.overlaps(_expand(booked, buffer_minutes)):
            return True
    return False


def _within_hours(candidate: Interval, day_hours: DayHours, tz_name: str | None) -> bool:
    """Candidate must fall entirely inside that weekday's opening hours,
    evaluated in the business's local timezone."""
    if not day_hours.is_open or day_hours.open_time is None or day_hours.close_time is None:
        return False

    tz = get_tz(tz_name)
    local_start = candidate.start.astimezone(tz)
    local_end = candidate.end.astimezone(tz)

    # Must not span past midnight into a different day's hours.
    if local_start.date() != local_end.date():
        return False
    if local_start.weekday() != day_hours.weekday:
        return False

    open_dt = local_start.replace(
        hour=day_hours.open_time.hour, minute=day_hours.open_time.minute, second=0, microsecond=0
    )
    close_dt = local_start.replace(
        hour=day_hours.close_time.hour, minute=day_hours.close_time.minute, second=0, microsecond=0
    )
    return open_dt <= local_start and local_end <= close_dt


@dataclass(frozen=True)
class SlotCheck:
    available: bool
    reason: str | None = None  # machine-readable: past | too_soon | too_far | closed | conflict


def check_slot(
    start_utc: datetime,
    rules: Rules,
    day_hours: DayHours,
    existing: list[Interval],
    tz_name: str | None,
    now: datetime | None = None,
) -> SlotCheck:
    """The single source of truth for 'can this exact slot be booked?'."""
    now = _as_utc(now) if now else now_utc()
    start_utc = _as_utc(start_utc)
    end_utc = start_utc + timedelta(minutes=rules.slot_duration_minutes)
    candidate = Interval(start_utc, end_utc)

    if start_utc <= now:
        return SlotCheck(False, "past")
    if start_utc < now + timedelta(minutes=rules.min_notice_minutes):
        return SlotCheck(False, "too_soon")
    if start_utc > now + timedelta(days=rules.max_advance_days):
        return SlotCheck(False, "too_far")
    if not _within_hours(candidate, day_hours, tz_name):
        return SlotCheck(False, "closed")
    if has_conflict(candidate, existing, rules.buffer_minutes):
        return SlotCheck(False, "conflict")
    return SlotCheck(True, None)


def generate_slots(
    day: "datetime.date",
    rules: Rules,
    day_hours: DayHours,
    existing: list[Interval],
    tz_name: str | None,
    now: datetime | None = None,
) -> list[datetime]:
    """Every open, conflict-free slot start (as UTC datetimes) for one local day."""
    if not day_hours.is_open or day_hours.open_time is None or day_hours.close_time is None:
        return []

    tz = get_tz(tz_name)
    now = _as_utc(now) if now else now_utc()

    cursor_local = datetime.combine(day, day_hours.open_time).replace(tzinfo=tz)
    close_local = datetime.combine(day, day_hours.close_time).replace(tzinfo=tz)
    step = timedelta(minutes=rules.slot_duration_minutes)

    slots: list[datetime] = []
    while cursor_local + step <= close_local:
        start_utc = cursor_local.astimezone(timezone.utc)
        check = check_slot(start_utc, rules, day_hours, existing, tz_name, now=now)
        if check.available:
            slots.append(start_utc)
        cursor_local += step
    return slots
