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

from app.config import get_settings
from app.database import SessionLocal
from app.logging_config import configure_logging, get_logger
from app.services.reminders.reminder_service import ReminderService

_settings = get_settings()
configure_logging(_settings.app_env, _settings.log_level)
logger = get_logger(__name__)


def run_once() -> int:
    db = SessionLocal()
    try:
        count = ReminderService(db).run_once()
        logger.info("reminders.run_completed", extra={"ctx": {"event": "reminders.run_completed", "sent": count}})
        return count
    finally:
        db.close()


def run_loop(interval_seconds: int = 300):
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        logger.warning("reminders.apscheduler_missing", extra={"ctx": {"event": "reminders.apscheduler_missing"}})
        import time
        while True:
            run_once()
            time.sleep(interval_seconds)
        return

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_once, "interval", seconds=interval_seconds, id="reminders")
    logger.info("reminders.scheduler_started", extra={"ctx": {"event": "reminders.scheduler_started", "interval_seconds": interval_seconds}})
    run_once()
    scheduler.start()


if __name__ == "__main__":
    if "--loop" in sys.argv:
        run_loop()
    else:
        run_once()
