"""
Phase 10C: the explicit action-type -> handler registry that
AIActionApprovalService.approve_and_execute() invokes AFTER a human
approves an AIActionApproval - never before, never automatically, and
never merely because status became "approved" (that alone is only a
decision record - see approval_service.py's docstring). Each handler
re-fetches the current DB state for the identifiers named in the
approval's payload and executes through the SAME authoritative service
a human dashboard action already uses (AppointmentService/GmailService)
- never a raw ORM/SQL mutation, and never eval()/arbitrary dispatch of
the stored payload; only a fixed, explicit mapping from action_type to
one specific function.

An action_type with no registered handler here (schedule_site_visit,
create_follow_up, customer_message_draft) stays proposal-only forever -
see realestate_visit_followup_tools.py's module docstring for why.
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app import models
from app.services.scheduling.appointment_service import AppointmentService
from app.services.gmail.gmail_service import GmailService


def _execute_confirm_site_visit(db: Session, agency: models.Agency, approval: models.AIActionApproval) -> dict:
    appointment_id = approval.payload.get("appointment_id")
    if not appointment_id:
        return {"executed": False, "service": "AppointmentService.confirm", "outcome": "missing_appointment_id"}
    outcome = AppointmentService(db).confirm(agency, appointment_id)
    return {
        "executed": outcome.ok, "service": "AppointmentService.confirm",
        "outcome": outcome.reason or ("confirmed" if outcome.ok else "failed"),
        "message": outcome.message,
    }


def _execute_reschedule_site_visit(db: Session, agency: models.Agency, approval: models.AIActionApproval) -> dict:
    appointment_id = approval.payload.get("appointment_id")
    new_start_local_iso = approval.payload.get("new_start_local_iso")
    if not (appointment_id and new_start_local_iso):
        return {"executed": False, "service": "AppointmentService.reschedule", "outcome": "missing_arguments"}
    outcome = AppointmentService(db).reschedule(agency, appointment_id, new_start_local_iso)
    return {
        "executed": outcome.ok, "service": "AppointmentService.reschedule",
        "outcome": outcome.reason or ("rescheduled" if outcome.ok else "failed"),
        "message": outcome.message,
    }


def _execute_cancel_site_visit(db: Session, agency: models.Agency, approval: models.AIActionApproval) -> dict:
    appointment_id = approval.payload.get("appointment_id")
    if not appointment_id:
        return {"executed": False, "service": "AppointmentService.cancel", "outcome": "missing_appointment_id"}
    outcome = AppointmentService(db).cancel(agency, appointment_id)
    return {
        "executed": outcome.ok, "service": "AppointmentService.cancel",
        "outcome": outcome.reason or ("cancelled" if outcome.ok else "failed"),
        "message": outcome.message,
    }


def _execute_send_customer_message(db: Session, agency: models.Agency, approval: models.AIActionApproval) -> dict:
    to = approval.payload.get("to")
    body = approval.payload.get("body")
    subject = approval.payload.get("subject") or ""
    if not (to and body):
        return {"executed": False, "service": "GmailService.send", "outcome": "missing_arguments"}
    result = GmailService(db).send(agency, to=to, subject=subject, body=body, employee=approval.requested_by_employee)
    # GmailService.send() enforces the agency's own existing send_mode/
    # GmailPendingAction control - "executed" here means "handed to the
    # real, authoritative Gmail send path", NOT necessarily "actually
    # delivered". Its own ok/sent/queued_for_approval/error distinctions
    # are preserved verbatim in `outcome` - never collapsed into a
    # fabricated "sent" claim.

    # Final Hardening: CONTACTED = "a verified outbound communication
    # event", never merely "an approval was approved" - only when
    # result["sent"] is True (a real, immediate send - never
    # "queued_for_approval").
    if result.get("sent") is True:
        lead_id = approval.payload.get("lead_id")
        if lead_id:
            lead = db.query(models.Lead).filter(models.Lead.id == lead_id, models.Lead.agency_id == agency.id).first()
            if lead is not None:
                from app.services.marketplace import lead_lifecycle
                lead_lifecycle.system_advance(
                    db, lead, agency.id, "contacted",
                    caused_by=f"customer message sent (approval {approval.id})",
                )

    return {"executed": result.get("ok", False), "service": "GmailService.send", "outcome": result}


ACTION_HANDLERS: dict[str, Callable[[Session, models.Agency, models.AIActionApproval], dict]] = {
    "confirm_site_visit": _execute_confirm_site_visit,
    "reschedule_site_visit": _execute_reschedule_site_visit,
    "cancel_site_visit": _execute_cancel_site_visit,
    "send_customer_message": _execute_send_customer_message,
}


def execute_approved_action(db: Session, agency: models.Agency, approval: models.AIActionApproval) -> dict | None:
    """Returns None if `approval.action_type` has no registered handler -
    that action_type stays proposal-only; callers must treat None as
    "nothing to execute", never as a failure."""
    handler = ACTION_HANDLERS.get(approval.action_type)
    if handler is None:
        return None
    return handler(db, agency, approval)
