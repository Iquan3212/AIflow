"""
Phase 10A, Step 1 (extended Phase 10C): site-visit and customer-outreach
tools for tool-calling-capable AI Workforce employees.

get_available_slots is read-only (real availability, via
app.services.scheduling.appointment_service.AppointmentService - the
same rules engine the customer-widget booking flow and the dashboard
already use).

Every other tool here - propose_visit, confirm_visit, reschedule_visit,
cancel_visit, create_follow_up, draft_customer_message,
propose_send_customer_message - never mutates a real Appointment/
Booking and never sends a real customer communication itself. Each one
only creates a pending
app.services.ai_workforce.approval_service.AIActionApproval record
describing the proposed action. As of Phase 10C, an APPROVED action of
one of the "consequential" types (reschedule_site_visit,
confirm_site_visit, cancel_site_visit, send_customer_message) IS wired
to real execution - see app.services.ai_workforce.action_execution's
explicit action-type -> handler registry, invoked only by
AIActionApprovalService.approve_and_execute(), never automatically. A
human approving is a necessary but not sufficient condition: execution
still re-validates against the current DB state through the same
authoritative service (AppointmentService/GmailService) a human
dashboard action would use - never a raw ORM/SQL mutation, never
eval()/arbitrary dispatch of the stored payload.

schedule_site_visit and create_follow_up/customer_message_draft remain
proposal-only with no execution wiring (Phase 10A/10C's booking
boundary: creating a brand-new booking-adjacent commitment is
recommendation-only, never auto-executed even after approval).

Same ToolRouter calling convention as every other tool in app/tools/:
execute(message, db, agency, conversation, lead, **kwargs). `agency` is
always the authenticated caller's own Agency; every lookup below is
scoped to `agency.id`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services.lead_service import LeadService
from app.services.inventory.property_service import PropertyService
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import parse_local_iso, humanize, to_local
from app.services.ai_workforce.approval_service import AIActionApprovalService

_DEFAULT_EMPLOYEE = "ai_workforce"


class GetAvailableSlotsTool:
    """get_available_slots(date_local) - real open slots for one day, in
    the agency's own timezone and scheduling rules."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, date_local: str = None, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not date_local:
            return {"success": False, "error": "missing_date_local"}

        from datetime import date as date_cls
        try:
            day = date_cls.fromisoformat(date_local)
        except ValueError:
            return {"success": False, "error": "invalid_date", "message": "date_local must be YYYY-MM-DD."}

        svc = AppointmentService(db)
        slots = svc.list_slots(agency, day)
        return {
            "success": True,
            "date": date_local,
            "slots": [
                {"start_local_iso": to_local(s, agency.timezone).strftime("%Y-%m-%dT%H:%M"), "label": humanize(s, agency.timezone)}
                for s in slots
            ],
        }


class ProposeVisitTool:
    """propose_visit(lead_id, property_id, start_local_iso) - proposes
    (never books) a site visit. Creates a pending AIActionApproval; no
    Appointment row is created by this tool."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, lead_id: str = None, property_id: str = None,
                start_local_iso: str = None, requested_by_employee: str = _DEFAULT_EMPLOYEE, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not (lead_id and property_id and start_local_iso):
            return {"success": False, "error": "missing_arguments"}

        lead_row = LeadService(db).get(lead_id, agency.id)
        if lead_row is None:
            return {"success": False, "error": "lead_not_found"}
        prop_row = PropertyService(db).get(property_id, agency.id)
        if prop_row is None:
            return {"success": False, "error": "property_not_found"}
        try:
            parse_local_iso(start_local_iso, agency.timezone)
        except (ValueError, TypeError):
            return {"success": False, "error": "invalid_datetime"}

        who = lead_row.name or lead_row.phone or lead_row.email or str(lead_row.id)
        where = prop_row.unit_number or str(prop_row.id)
        summary = f"AI proposes a site visit for lead {who} at unit {where} on {start_local_iso}."
        approval = AIActionApprovalService(db).request(
            agency.id, action_type="schedule_site_visit", summary=summary,
            payload={"lead_id": str(lead_id), "property_id": str(property_id), "start_local_iso": start_local_iso},
            requested_by_employee=requested_by_employee,
        )
        return {
            "success": True, "proposed": True, "approval_id": approval.id, "status": approval.status.value,
            "message": "Site visit proposed - pending human approval. No appointment has been booked yet.",
        }


class RescheduleVisitTool:
    """reschedule_visit(appointment_id, new_start_local_iso) - proposes
    (never performs) moving an already-scheduled site visit to a new
    time. Creates a pending AIActionApproval; the Appointment's time is
    not changed by this tool (Phase 10C: rescheduling is consequential -
    it re-checks availability and notifies the customer via
    AppointmentService.reschedule() - so it is approval-gated, same as
    confirm/cancel)."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, appointment_id: str = None, new_start_local_iso: str = None,
                requested_by_employee: str = _DEFAULT_EMPLOYEE, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not (appointment_id and new_start_local_iso):
            return {"success": False, "error": "missing_arguments"}

        appt = AppointmentService(db).repo.get(agency.id, appointment_id)
        if appt is None:
            return {"success": False, "error": "appointment_not_found"}
        try:
            parse_local_iso(new_start_local_iso, agency.timezone)
        except (ValueError, TypeError):
            return {"success": False, "error": "invalid_datetime"}

        summary = f"AI proposes rescheduling site visit {appointment_id} to {new_start_local_iso}."
        approval = AIActionApprovalService(db).request(
            agency.id, action_type="reschedule_site_visit", summary=summary,
            payload={"appointment_id": str(appointment_id), "new_start_local_iso": new_start_local_iso},
            requested_by_employee=requested_by_employee,
        )
        return {
            "success": True, "proposed": True, "approval_id": approval.id, "status": approval.status.value,
            "message": "Reschedule proposed - pending human approval. The appointment time has not changed.",
        }


class CancelVisitTool:
    """cancel_visit(appointment_id) - proposes (never performs) cancelling
    an already-scheduled site visit. Creates a pending AIActionApproval;
    the Appointment's status is not changed by this tool."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, appointment_id: str = None,
                requested_by_employee: str = _DEFAULT_EMPLOYEE, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not appointment_id:
            return {"success": False, "error": "missing_appointment_id"}

        appt = AppointmentService(db).repo.get(agency.id, appointment_id)
        if appt is None:
            return {"success": False, "error": "appointment_not_found"}

        summary = f"AI proposes cancelling site visit {appointment_id} scheduled for {appt.scheduled_at}."
        approval = AIActionApprovalService(db).request(
            agency.id, action_type="cancel_site_visit", summary=summary,
            payload={"appointment_id": str(appointment_id)}, requested_by_employee=requested_by_employee,
        )
        return {
            "success": True, "proposed": True, "approval_id": approval.id, "status": approval.status.value,
            "message": "Cancellation proposed - pending human approval. The appointment status has not changed.",
        }


class ConfirmVisitTool:
    """confirm_visit(appointment_id) - proposes (never performs) marking
    an already-scheduled site visit as confirmed. Creates a pending
    AIActionApproval; the Appointment's status is not changed by this
    tool."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, appointment_id: str = None,
                requested_by_employee: str = _DEFAULT_EMPLOYEE, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not appointment_id:
            return {"success": False, "error": "missing_appointment_id"}

        appt = AppointmentService(db).repo.get(agency.id, appointment_id)
        if appt is None:
            return {"success": False, "error": "appointment_not_found"}

        summary = f"AI proposes confirming site visit {appointment_id} scheduled for {appt.scheduled_at}."
        approval = AIActionApprovalService(db).request(
            agency.id, action_type="confirm_site_visit", summary=summary,
            payload={"appointment_id": str(appointment_id)}, requested_by_employee=requested_by_employee,
        )
        return {
            "success": True, "proposed": True, "approval_id": approval.id, "status": approval.status.value,
            "message": "Confirmation proposed - pending human approval. The appointment status has not changed.",
        }


class CreateFollowUpTool:
    """create_follow_up(lead_id, note) - proposes a follow-up action on a
    lead. No dedicated follow-up/task model exists in this codebase, and
    Step 1 of the Phase 10A spec says not to invent one - the
    AIActionApproval record itself IS the follow-up proposal; a human
    decides and acts on it (e.g. calling the lead back), nothing here
    schedules anything automatically."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, lead_id: str = None, note: str = None,
                due_local_iso: str = None, requested_by_employee: str = _DEFAULT_EMPLOYEE, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not (lead_id and note):
            return {"success": False, "error": "missing_arguments"}

        lead_row = LeadService(db).get(lead_id, agency.id)
        if lead_row is None:
            return {"success": False, "error": "lead_not_found"}

        who = lead_row.name or lead_row.phone or lead_row.email or str(lead_row.id)
        summary = f"AI proposes a follow-up for lead {who}: {note}"
        approval = AIActionApprovalService(db).request(
            agency.id, action_type="create_follow_up", summary=summary,
            payload={"lead_id": str(lead_id), "note": note, "due_local_iso": due_local_iso},
            requested_by_employee=requested_by_employee,
        )
        return {"success": True, "proposed": True, "approval_id": approval.id, "status": approval.status.value}


class DraftCustomerMessageTool:
    """draft_customer_message(lead_id, message_body) - drafts a message
    for human review, mirroring the existing GmailPendingAction/
    GmailDraftTool "draft, never auto-send" precedent. Creates a pending
    AIActionApproval; nothing is sent by this tool."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, lead_id: str = None, message_body: str = None,
                requested_by_employee: str = _DEFAULT_EMPLOYEE, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not (lead_id and message_body):
            return {"success": False, "error": "missing_arguments"}

        lead_row = LeadService(db).get(lead_id, agency.id)
        if lead_row is None:
            return {"success": False, "error": "lead_not_found"}

        who = lead_row.name or lead_row.phone or lead_row.email or str(lead_row.id)
        summary = f"AI drafted a message to lead {who} for review."
        approval = AIActionApprovalService(db).request(
            agency.id, action_type="customer_message_draft", summary=summary,
            payload={"lead_id": str(lead_id), "draft": message_body}, requested_by_employee=requested_by_employee,
        )
        return {
            "success": True, "proposed": True, "approval_id": approval.id, "status": approval.status.value,
            "message": "Draft saved for human review. Nothing was sent.",
        }


class ProposeSendCustomerMessageTool:
    """propose_send_customer_message(lead_id, message_body) - Phase 10C:
    proposes ACTUALLY SENDING a message to a lead, unlike
    DraftCustomerMessageTool above (which only ever creates a
    reviewable draft). Creates a pending AIActionApproval with
    action_type="send_customer_message"; nothing is sent by this tool.
    Only once a human approves it does execution attempt a real send -
    via GmailService.send() (see app.services.ai_workforce.
    action_execution), which enforces the agency's own existing Gmail
    send_mode/GmailPendingAction control exactly as it already does for
    every other Gmail-originated send. Requires the lead to have a real
    email address on file - never invents one."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, lead_id: str = None, message_body: str = None,
                subject: str = None, requested_by_employee: str = _DEFAULT_EMPLOYEE, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not (lead_id and message_body):
            return {"success": False, "error": "missing_arguments"}

        lead_row = LeadService(db).get(lead_id, agency.id)
        if lead_row is None:
            return {"success": False, "error": "lead_not_found"}
        if not lead_row.email:
            return {"success": False, "error": "lead_has_no_email", "message": "This lead has no email on file to send to."}

        who = lead_row.name or lead_row.phone or lead_row.email
        summary = f"AI proposes sending an email to lead {who} ({lead_row.email})."
        approval = AIActionApprovalService(db).request(
            agency.id, action_type="send_customer_message", summary=summary,
            payload={
                "lead_id": str(lead_id), "to": lead_row.email,
                "subject": subject or f"Following up - {agency.name}", "body": message_body,
            },
            requested_by_employee=requested_by_employee,
        )
        return {
            "success": True, "proposed": True, "approval_id": approval.id, "status": approval.status.value,
            "message": "Send proposed - pending human approval. Nothing has been sent yet.",
        }
