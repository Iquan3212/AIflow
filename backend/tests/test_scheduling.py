"""
Dependency-free tests for the pure scheduling logic.

Run: python3 -m tests.test_scheduling   (from backend/)  — no pytest needed.
These prove the correctness-critical behavior of Phase 3: conflict detection,
opening-hours enforcement, notice/advance windows, and DST-correct conversion.
"""

import sys
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")

from app.services.scheduling.availability import (
    Rules, DayHours, Interval, check_slot, generate_slots, has_conflict,
)
from app.services.scheduling.datetime_utils import parse_local_iso, to_local

IST = ZoneInfo("Asia/Kolkata")
_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


def utc(y, m, d, h, mi):
    """Build a UTC instant from an IST wall-clock time (helper for readability)."""
    return datetime(y, m, d, h, mi, tzinfo=IST).astimezone(timezone.utc)


# A Tuesday: 2026-08-04. Business open Tue 10:00–18:00 IST, 30-min slots.
TUE = datetime(2026, 8, 4).date()
HOURS_TUE = DayHours(weekday=1, is_open=True, open_time=time(10, 0), close_time=time(18, 0))
RULES = Rules(slot_duration_minutes=30, buffer_minutes=0, min_notice_minutes=60, max_advance_days=60)
# "now" fixed well before that Tuesday so notice/advance windows are satisfied.
NOW = utc(2026, 8, 3, 9, 0)


def test_iso_parse_and_tz():
    got = parse_local_iso("2026-08-04T16:00", "Asia/Kolkata")
    # 16:00 IST == 10:30 UTC
    check("ISO local parse -> UTC (IST 16:00 == 10:30Z)",
          got == datetime(2026, 8, 4, 10, 30, tzinfo=timezone.utc))
    back = to_local(got, "Asia/Kolkata")
    check("round-trips back to 16:00 local", back.hour == 16 and back.minute == 0)


def test_within_hours():
    ok = check_slot(utc(2026, 8, 4, 16, 0), RULES, HOURS_TUE, [], "Asia/Kolkata", now=NOW)
    check("16:00 IST is inside 10-18 -> available", ok.available)

    early = check_slot(utc(2026, 8, 4, 9, 0), RULES, HOURS_TUE, [], "Asia/Kolkata", now=NOW)
    check("09:00 IST before open -> closed", not early.available and early.reason == "closed")

    # last valid start is 17:30 (ends 18:00); 17:45 would end 18:15 -> closed
    late = check_slot(utc(2026, 8, 4, 17, 45), RULES, HOURS_TUE, [], "Asia/Kolkata", now=NOW)
    check("17:45 start ends after close -> closed", not late.available and late.reason == "closed")


def test_conflict_detection():
    existing = [Interval(utc(2026, 8, 4, 16, 0), utc(2026, 8, 4, 16, 30))]
    dup = check_slot(utc(2026, 8, 4, 16, 0), RULES, HOURS_TUE, existing, "Asia/Kolkata", now=NOW)
    check("exact double-book -> conflict", not dup.available and dup.reason == "conflict")

    overlap = check_slot(utc(2026, 8, 4, 16, 15), RULES, HOURS_TUE, existing, "Asia/Kolkata", now=NOW)
    check("partial overlap -> conflict", not overlap.available and overlap.reason == "conflict")

    adjacent = check_slot(utc(2026, 8, 4, 16, 30), RULES, HOURS_TUE, existing, "Asia/Kolkata", now=NOW)
    check("back-to-back (no buffer) -> allowed", adjacent.available)


def test_buffer():
    rules = Rules(slot_duration_minutes=30, buffer_minutes=15, min_notice_minutes=60, max_advance_days=60)
    existing = [Interval(utc(2026, 8, 4, 16, 0), utc(2026, 8, 4, 16, 30))]
    adjacent = check_slot(utc(2026, 8, 4, 16, 30), rules, HOURS_TUE, existing, "Asia/Kolkata", now=NOW)
    check("back-to-back with 15m buffer -> conflict", not adjacent.available)
    clear = check_slot(utc(2026, 8, 4, 16, 45), rules, HOURS_TUE, existing, "Asia/Kolkata", now=NOW)
    check("45m gap clears the 15m buffer -> allowed", clear.available)


def test_notice_and_advance():
    soon = check_slot(utc(2026, 8, 3, 9, 30), RULES, HOURS_TUE, [], "Asia/Kolkata", now=NOW)
    check("30m out with 60m notice -> too_soon", not soon.available and soon.reason == "too_soon")

    far_rules = Rules(max_advance_days=7, slot_duration_minutes=30, min_notice_minutes=60)
    far = check_slot(utc(2026, 8, 20, 16, 0), far_rules, HOURS_TUE, [], "Asia/Kolkata", now=NOW)
    check("beyond max_advance_days -> too_far", not far.available and far.reason == "too_far")

    past = check_slot(utc(2026, 8, 3, 8, 0), RULES, HOURS_TUE, [], "Asia/Kolkata", now=NOW)
    check("in the past -> past", not past.available and past.reason == "past")


def test_generate_slots():
    # 10:00–18:00, 30-min slots, empty calendar -> 16 slots, first 10:00, last 17:30.
    slots = generate_slots(TUE, RULES, HOURS_TUE, [], "Asia/Kolkata", now=NOW)
    check("empty Tuesday -> 16 open slots", len(slots) == 16)
    check("first slot 10:00 IST", to_local(slots[0], "Asia/Kolkata").hour == 10)
    check("last slot 17:30 IST", to_local(slots[-1], "Asia/Kolkata").strftime("%H:%M") == "17:30")

    # Book 16:00; that slot should disappear, count drops to 15.
    existing = [Interval(utc(2026, 8, 4, 16, 0), utc(2026, 8, 4, 16, 30))]
    slots2 = generate_slots(TUE, RULES, HOURS_TUE, existing, "Asia/Kolkata", now=NOW)
    check("one booking removes exactly one slot", len(slots2) == 15)
    check("16:00 no longer offered",
          all(to_local(s, "Asia/Kolkata").strftime("%H:%M") != "16:00" for s in slots2))


def test_closed_day():
    sun = datetime(2026, 8, 9).date()  # Sunday
    closed = DayHours(weekday=6, is_open=False, open_time=None, close_time=None)
    check("closed weekday -> no slots",
          generate_slots(sun, RULES, closed, [], "Asia/Kolkata", now=NOW) == [])


if __name__ == "__main__":
    for fn in [
        test_iso_parse_and_tz, test_within_hours, test_conflict_detection,
        test_buffer, test_notice_and_advance, test_generate_slots, test_closed_day,
    ]:
        print(f"\n{fn.__name__}:")
        fn()
    print(f"\n{'='*50}\n{_passed} passed, {_failed} failed\n{'='*50}")
    sys.exit(1 if _failed else 0)
