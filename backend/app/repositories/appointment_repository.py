"""
Data access for appointments. Uses the request-scoped Session passed in (never
opens its own), so a booking + its side effects share one transaction.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app import models


class AppointmentRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- writes -------------------------------------------------------------

    def add(self, appointment: models.Appointment) -> models.Appointment:
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def save(self, appointment: models.Appointment) -> models.Appointment:
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    # ---- reads --------------------------------------------------------------

    def get(self, business_id: str, appointment_id: str) -> models.Appointment | None:
        return (
            self.db.query(models.Appointment)
            .filter(
                models.Appointment.id == appointment_id,
                models.Appointment.business_id == business_id,
            )
            .first()
        )

    def get_all(self, business_id: str) -> list[models.Appointment]:
        return (
            self.db.query(models.Appointment)
            .filter(models.Appointment.business_id == business_id)
            .order_by(models.Appointment.scheduled_at.desc())
            .all()
        )

    def get_active_on_day(
        self, business_id: str, day_start_utc: datetime, day_end_utc: datetime
    ) -> list[models.Appointment]:
        """Non-cancelled appointments whose start falls in [day_start, day_end)."""
        return (
            self.db.query(models.Appointment)
            .filter(
                models.Appointment.business_id == business_id,
                models.Appointment.status != models.AppointmentStatus.cancelled,
                models.Appointment.scheduled_at >= day_start_utc,
                models.Appointment.scheduled_at < day_end_utc,
            )
            .all()
        )

    def get_overlapping(
        self,
        business_id: str,
        start_utc: datetime,
        end_utc: datetime,
        exclude_id: str | None = None,
    ) -> list[models.Appointment]:
        """Any non-cancelled appointment whose [scheduled_at, end_at) overlaps
        [start_utc, end_utc). This is the DB-side conflict guard that backs up
        the in-memory check_slot — the last line of defense against a race."""
        q = self.db.query(models.Appointment).filter(
            models.Appointment.business_id == business_id,
            models.Appointment.status != models.AppointmentStatus.cancelled,
            and_(
                models.Appointment.scheduled_at < end_utc,
                models.Appointment.end_at > start_utc,
            ),
        )
        if exclude_id:
            q = q.filter(models.Appointment.id != exclude_id)
        return q.all()

    def get_due_reminders(
        self, within: timedelta, now_utc: datetime | None = None
    ) -> list[models.Appointment]:
        """Upcoming, un-reminded, non-cancelled appointments starting inside the
        next `within` window. Drives the reminder worker across all tenants."""
        now = now_utc or datetime.now(timezone.utc)
        horizon = now + within
        return (
            self.db.query(models.Appointment)
            .filter(
                models.Appointment.status.in_(
                    [models.AppointmentStatus.scheduled, models.AppointmentStatus.confirmed]
                ),
                models.Appointment.reminder_sent_at.is_(None),
                models.Appointment.scheduled_at > now,
                models.Appointment.scheduled_at <= horizon,
            )
            .all()
        )
