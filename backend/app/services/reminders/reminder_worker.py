"""
Reminder worker entrypoint.

Two ways to run it:

  1. Cron / scheduled task (simplest, no extra deps):
       */5 * * * *  cd /path/to/backend && python -m app.services.reminders.reminder_worker

  2. Long-running scheduler (if APScheduler is installed):
       python -m app.services.reminders.reminder_worker --loop

Both call ReminderService.run_once, which is idempotent.
"""

from __future__ import annotations

import sys

from app.database import SessionLocal
from app.services.reminders.reminder_service import ReminderService


def run_once() -> int:
    db = SessionLocal()
    try:
        count = ReminderService(db).run_once()
        print(f"[reminders] sent {count} reminder(s)")
        return count
    finally:
        db.close()


def run_loop(interval_seconds: int = 300):
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        print("APScheduler not installed; falling back to a simple sleep loop.")
        import time
        while True:
            run_once()
            time.sleep(interval_seconds)
        return

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_once, "interval", seconds=interval_seconds, id="reminders")
    print(f"[reminders] scheduler started (every {interval_seconds}s). Ctrl-C to stop.")
    run_once()
    scheduler.start()


if __name__ == "__main__":
    if "--loop" in sys.argv:
        run_loop()
    else:
        run_once()
