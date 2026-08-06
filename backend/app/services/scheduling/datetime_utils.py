"""
Timezone handling for the scheduler.

Contract: the LLM resolves a customer's fuzzy phrasing ("tomorrow at 4pm") into
a plain ISO-8601 *local* datetime string, because it is given the business's
current date and timezone in the system prompt and is reliable at that step.
The backend never trusts that blindly — it parses the ISO value, attaches the
business timezone, and converts to UTC, which is the single canonical form we
store and compare. This keeps all the hard correctness (DST, overlap, "is this
in the past") in deterministic Python, not in the model.
"""

from __future__ import annotations

from datetime import datetime, timezone, date, time
from zoneinfo import ZoneInfo


DEFAULT_TZ = "Asia/Kolkata"


def get_tz(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_local_iso(value: str, tz_name: str | None) -> datetime:
    """Parse an ISO-8601 datetime that represents *local* wall-clock time in the
    business timezone, and return a timezone-aware UTC datetime.

    Accepts 'YYYY-MM-DDTHH:MM', 'YYYY-MM-DD HH:MM', with optional seconds.
    If the string already carries an offset/Z, that offset is respected.
    Raises ValueError on anything unparseable.
    """
    tz = get_tz(tz_name)
    raw = value.strip().replace(" ", "T", 1)

    # Support a trailing 'Z' (UTC) which fromisoformat historically rejected.
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    dt = datetime.fromisoformat(raw)  # raises ValueError if malformed

    if dt.tzinfo is None:
        # Naive => interpret as local wall-clock in the business timezone.
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def combine_local(d: date, t: time, tz_name: str | None) -> datetime:
    """Combine a local date + time into a UTC datetime."""
    tz = get_tz(tz_name)
    return datetime.combine(d, t).replace(tzinfo=tz).astimezone(timezone.utc)


def to_local(dt_utc: datetime, tz_name: str | None) -> datetime:
    """Render a stored UTC datetime back into the business timezone."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(get_tz(tz_name))


def humanize(dt_utc: datetime, tz_name: str | None) -> str:
    """Customer-facing string, e.g. 'Tuesday, 04 Aug 2026 at 4:00 PM'."""
    local = to_local(dt_utc, tz_name)
    return local.strftime("%A, %d %b %Y at %-I:%M %p") if _supports_dash() \
        else local.strftime("%A, %d %b %Y at %I:%M %p").replace(" 0", " ")


def _supports_dash() -> bool:
    # %-I works on Linux/macOS, not Windows. Cheap capability probe.
    try:
        datetime(2020, 1, 1, 4, 0).strftime("%-I")
        return True
    except ValueError:
        return False
