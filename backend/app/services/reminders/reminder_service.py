"""
Sends appointment reminders. Idempotent: an appointment is only reminded once
(guarded by reminder_sent_at), so running the worker every few minutes is safe.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app import models
from app.repositories.appointment_repository import AppointmentRepository
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.scheduling.datetime_utils import humanize, now_utc


class ReminderService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AppointmentRepository(db)
        self.notifier = NotificationDispatcher()

    def run_once(self, lookahead_hours: int = 24) -> int:
        """Send reminders for appointments starting within `lookahead_hours`.
        Returns how many were sent. Call on a schedule (e.g. every 5 minutes)."""
        due = self.repo.get_due_reminders(within=timedelta(hours=lookahead_hours))
        sent = 0
        for appt in due:
            business = appt.business
            when = humanize(appt.scheduled_at, business.timezone)
            body = (f"Reminder: you have an appointment with {business.name} "
                    f"on {when}. Reply here if you need to reschedule or cancel.")
            results = self.notifier.notify_customer(
                name=appt.customer_name,
                email=appt.customer_email,
                phone=appt.customer_phone,
                subject=f"Reminder — appointment with {business.name}",
                body=body,
            )
            if any(r.ok for r in results):
                appt.reminder_sent_at = now_utc()
                self.repo.save(appt)
                sent += 1
        return sent
