"""
The controlled status lifecycle for Phase 9's new agency confirm/
complete/no-show actions - mirrors app/services/inventory/status.py's
exact "validated, not just documented" discipline. This governs ONLY
these three new explicit agency actions; book()/reschedule()/cancel()
are completely untouched and continue setting
scheduled/rescheduled/cancelled exactly as they always have.
"""

from __future__ import annotations

from app.models import AppointmentStatus

ALLOWED_APPOINTMENT_ACTION_TRANSITIONS: dict[AppointmentStatus, frozenset[AppointmentStatus]] = {
    AppointmentStatus.scheduled: frozenset({AppointmentStatus.confirmed}),
    AppointmentStatus.confirmed: frozenset({AppointmentStatus.completed, AppointmentStatus.no_show}),
}


class InvalidAppointmentActionError(ValueError):
    def __init__(self, current: AppointmentStatus, requested: AppointmentStatus):
        self.current = current
        self.requested = requested
        super().__init__(
            f"Cannot change appointment status from '{current.value}' to '{requested.value}'."
        )


def validate_appointment_action(current: AppointmentStatus, requested: AppointmentStatus) -> None:
    """Raises InvalidAppointmentActionError unless the transition is
    allowed. Setting a status to its own current value is always a
    no-op, never an error - the same rule Property's own status.py
    uses, so retrying an already-applied confirm/complete/no-show is
    harmless rather than a 409."""
    if current == requested:
        return
    if requested not in ALLOWED_APPOINTMENT_ACTION_TRANSITIONS.get(current, frozenset()):
        raise InvalidAppointmentActionError(current, requested)
