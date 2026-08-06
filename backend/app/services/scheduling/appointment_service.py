"""
Appointment orchestration. Combines the pure availability logic with the DB,
the calendar adapter, and customer notifications. This is what the chat tools
and the dashboard endpoints both call, so booking rules live in exactly one
place.
"""

from __future__ import annotations

from datetime import datetime, timedelta, time, timezone
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import models
from app.repositories.appointment_repository import AppointmentRepository
from app.services.calendar.factory import get_calendar_for
from app.services.calendar.base import CalendarEvent
from app.services.notifications.dispatcher import NotificationDispatcher

from .availability import Rules, DayHours, Interval, check_slot, generate_slots
from .datetime_utils import parse_local_iso, to_local, humanize, get_tz, now_utc


# Default opening hours seeded for a new business: Mon–Sat 10:00–18:00, Sun closed.
_DEFAULT_HOURS = {wd: (time(10, 0), time(18, 0)) for wd in range(0, 6)}  # Mon..Sat


@dataclass
class BookingOutcome:
    ok: bool
    appointment: models.Appointment | None = None
    reason: str | None = None          # machine-readable when ok is False
    message: str = ""                  # human/customer-facing message
    alternatives: list[str] | None = None  # humanized alternative slots


class AppointmentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AppointmentRepository(db)
        self.notifier = NotificationDispatcher()

    # ---- per-tenant config --------------------------------------------------

    def ensure_defaults(self, business: models.Business) -> None:
        """Seed default hours + settings so a brand-new business can book today."""
        if not business.scheduling_settings:
            self.db.add(models.SchedulingSettings(business_id=business.id))
        existing = {h.weekday for h in business.business_hours}
        for wd in range(7):
            if wd in existing:
                continue
            if wd in _DEFAULT_HOURS:
                o, c = _DEFAULT_HOURS[wd]
                self.db.add(models.BusinessHours(
                    business_id=business.id, weekday=wd, is_open=True, open_time=o, close_time=c
                ))
            else:
                self.db.add(models.BusinessHours(
                    business_id=business.id, weekday=wd, is_open=False
                ))
        self.db.commit()
        self.db.refresh(business)

    def _rules(self, business: models.Business) -> Rules:
        s = business.scheduling_settings
        if not s:
            return Rules()
        return Rules(
            slot_duration_minutes=s.slot_duration_minutes,
            buffer_minutes=s.buffer_minutes,
            min_notice_minutes=s.min_notice_minutes,
            max_advance_days=s.max_advance_days,
        )

    def _day_hours(self, business: models.Business, weekday: int) -> DayHours:
        for h in business.business_hours:
            if h.weekday == weekday:
                return DayHours(weekday, h.is_open, h.open_time, h.close_time)
        return DayHours(weekday, False, None, None)

    def _existing_intervals(self, business_id: str, day_local, tz_name: str) -> list[Interval]:
        tz = get_tz(tz_name)
        start_local = datetime.combine(day_local, time(0, 0)).replace(tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        rows = self.repo.get_active_on_day(
            business_id, start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
        )
        return [Interval(_utc(r.scheduled_at), _utc(r.end_at)) for r in rows]

    # ---- availability -------------------------------------------------------

    def list_slots(self, business: models.Business, day_local) -> list[datetime]:
        self.ensure_defaults(business)
        tz = business.timezone
        return generate_slots(
            day_local,
            self._rules(business),
            self._day_hours(business, day_local.weekday()),
            self._existing_intervals(business.id, day_local, tz),
            tz,
        )

    def is_available(self, business: models.Business, start_utc: datetime):
        self.ensure_defaults(business)
        tz = business.timezone
        local = to_local(start_utc, tz)
        return check_slot(
            start_utc,
            self._rules(business),
            self._day_hours(business, local.weekday()),
            self._existing_intervals(business.id, local.date(), tz),
            tz,
        )

    def _humanized_alternatives(self, business, start_utc, limit=3) -> list[str]:
        """A few nearby open slots to offer when the requested one is taken."""
        tz = business.timezone
        out: list[str] = []
        for offset in range(0, 8):  # search up to a week ahead
            day = (to_local(start_utc, tz) + timedelta(days=offset)).date()
            for slot in self.list_slots(business, day):
                if slot > now_utc():
                    out.append(humanize(slot, tz))
                    if len(out) >= limit:
                        return out
        return out

    # ---- book / reschedule / cancel ----------------------------------------

    def book(
        self,
        business: models.Business,
        *,
        start_local_iso: str,
        customer_name: str | None,
        customer_phone: str | None,
        customer_email: str | None,
        service: str | None = None,
        lead_id: str | None = None,
        conversation_id: str | None = None,
        source: str = "chat",
    ) -> BookingOutcome:
        self.ensure_defaults(business)
        tz = business.timezone

        try:
            start_utc = parse_local_iso(start_local_iso, tz)
        except (ValueError, TypeError):
            return BookingOutcome(False, reason="bad_datetime",
                                  message="I couldn't understand that date and time. Could you give a specific day and time?")

        rules = self._rules(business)
        check = self.is_available(business, start_utc)
        if not check.available:
            alts = self._humanized_alternatives(business, start_utc)
            return BookingOutcome(
                False, reason=check.reason,
                message=_reason_message(check.reason, humanize(start_utc, tz)),
                alternatives=alts,
            )

        end_utc = start_utc + timedelta(minutes=rules.slot_duration_minutes)

        # DB-side conflict guard: re-check against the DB right before insert so a
        # race between two near-simultaneous bookings can't create a double-book.
        if self.repo.get_overlapping(business.id, start_utc, end_utc):
            alts = self._humanized_alternatives(business, start_utc)
            return BookingOutcome(False, reason="conflict",
                                  message=f"That slot ({humanize(start_utc, tz)}) was just taken.",
                                  alternatives=alts)

        appt = models.Appointment(
            business_id=business.id,
            lead_id=lead_id,
            conversation_id=conversation_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            service=service,
            scheduled_at=start_utc,
            end_at=end_utc,
            duration_minutes=rules.slot_duration_minutes,
            status=models.AppointmentStatus.scheduled,
            source=source,
        )
        appt = self.repo.add(appt)

        self._sync_calendar_create(business, appt)
        self._send_confirmation(business, appt)
        return BookingOutcome(True, appointment=appt,
                              message=f"Booked for {humanize(start_utc, tz)}.")

    def reschedule(self, business: models.Business, appointment_id: str, new_start_local_iso: str) -> BookingOutcome:
        self.ensure_defaults(business)
        tz = business.timezone
        appt = self.repo.get(business.id, appointment_id)
        if not appt or appt.status == models.AppointmentStatus.cancelled:
            return BookingOutcome(False, reason="not_found", message="I couldn't find that appointment.")

        try:
            start_utc = parse_local_iso(new_start_local_iso, tz)
        except (ValueError, TypeError):
            return BookingOutcome(False, reason="bad_datetime",
                                  message="I couldn't understand that new time. Could you give a specific day and time?")

        rules = self._rules(business)
        check = self.is_available(business, start_utc)
        # is_available counts the appointment's own current slot as "existing";
        # exclude it so moving to an overlapping-with-itself time still works.
        end_utc = start_utc + timedelta(minutes=rules.slot_duration_minutes)
        if not check.available and check.reason == "conflict":
            if not self.repo.get_overlapping(business.id, start_utc, end_utc, exclude_id=appt.id):
                check = type(check)(True, None)
        if not check.available:
            alts = self._humanized_alternatives(business, start_utc)
            return BookingOutcome(False, reason=check.reason,
                                  message=_reason_message(check.reason, humanize(start_utc, tz)),
                                  alternatives=alts)

        appt.scheduled_at = start_utc
        appt.end_at = end_utc
        appt.status = models.AppointmentStatus.rescheduled
        appt.reminder_sent_at = None  # re-arm the reminder for the new time
        appt = self.repo.save(appt)

        self._sync_calendar_update(business, appt)
        self._send_reschedule(business, appt)
        return BookingOutcome(True, appointment=appt,
                              message=f"Moved to {humanize(start_utc, tz)}.")

    def cancel(self, business: models.Business, appointment_id: str) -> BookingOutcome:
        tz = business.timezone
        appt = self.repo.get(business.id, appointment_id)
        if not appt:
            return BookingOutcome(False, reason="not_found", message="I couldn't find that appointment.")
        if appt.status == models.AppointmentStatus.cancelled:
            return BookingOutcome(True, appointment=appt, message="That appointment was already cancelled.")

        appt.status = models.AppointmentStatus.cancelled
        appt = self.repo.save(appt)
        self._sync_calendar_delete(business, appt)
        self._send_cancellation(business, appt)
        return BookingOutcome(True, appointment=appt,
                              message=f"Cancelled your appointment on {humanize(appt.scheduled_at, tz)}.")

    def find_for_customer(self, business: models.Business, *, phone=None, email=None, conversation_id=None):
        """Best-effort lookup of a customer's active appointment for reschedule/cancel."""
        for appt in self.repo.get_all(business.id):
            if appt.status == models.AppointmentStatus.cancelled:
                continue
            if conversation_id and appt.conversation_id == conversation_id:
                return appt
            if phone and appt.customer_phone == phone:
                return appt
            if email and appt.customer_email and email and appt.customer_email.lower() == email.lower():
                return appt
        return None

    # ---- side effects (calendar + notifications) ----------------------------

    def _event(self, business, appt) -> CalendarEvent:
        title = f"{appt.service or 'Appointment'} — {appt.customer_name or 'Customer'}"
        return CalendarEvent(
            summary=title,
            description=f"Booked via AIFlow.\nPhone: {appt.customer_phone or '-'}\nEmail: {appt.customer_email or '-'}",
            start_utc=_utc(appt.scheduled_at),
            end_utc=_utc(appt.end_at),
            attendee_email=appt.customer_email,
        )

    def _sync_calendar_create(self, business, appt):
        cal = get_calendar_for(business, self.db)
        try:
            event_id = cal.create_event(business, self._event(business, appt))
            if event_id:
                appt.calendar_provider = cal.provider
                appt.calendar_event_id = event_id
                self.repo.save(appt)
        except Exception as exc:
            print(f"[calendar:create:error] {exc}")

    def _sync_calendar_update(self, business, appt):
        if not appt.calendar_event_id:
            return
        try:
            get_calendar_for(business, self.db).update_event(business, appt.calendar_event_id, self._event(business, appt))
        except Exception as exc:
            print(f"[calendar:update:error] {exc}")

    def _sync_calendar_delete(self, business, appt):
        if not appt.calendar_event_id:
            return
        try:
            get_calendar_for(business, self.db).delete_event(business, appt.calendar_event_id)
        except Exception as exc:
            print(f"[calendar:delete:error] {exc}")

    def _send_confirmation(self, business, appt):
        when = humanize(appt.scheduled_at, business.timezone)
        body = (f"Hi {appt.customer_name or 'there'}, your appointment with {business.name} "
                f"is confirmed for {when}. Reply to this message if you need to change it.")
        self.notifier.notify_customer(
            name=appt.customer_name, email=appt.customer_email, phone=appt.customer_phone,
            subject=f"Appointment confirmed — {business.name}", body=body,
        )
        appt.confirmation_sent_at = now_utc()
        self.repo.save(appt)

    def _send_reschedule(self, business, appt):
        when = humanize(appt.scheduled_at, business.timezone)
        self.notifier.notify_customer(
            name=appt.customer_name, email=appt.customer_email, phone=appt.customer_phone,
            subject=f"Appointment updated — {business.name}",
            body=f"Your appointment with {business.name} has been moved to {when}.",
        )

    def _send_cancellation(self, business, appt):
        self.notifier.notify_customer(
            name=appt.customer_name, email=appt.customer_email, phone=appt.customer_phone,
            subject=f"Appointment cancelled — {business.name}",
            body=f"Your appointment with {business.name} has been cancelled.",
        )


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _reason_message(reason: str | None, when: str) -> str:
    return {
        "past": "That time is in the past. What upcoming day works for you?",
        "too_soon": "That's a bit too soon to book. Could you pick a later time?",
        "too_far": "That's further out than we can book right now.",
        "closed": f"We're closed at {when}. Here are some open times instead:",
        "conflict": f"Sorry, {when} is already booked. Here are some nearby openings:",
    }.get(reason or "", "That time doesn't work. Here are some alternatives:")
