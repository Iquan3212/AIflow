"""
Phase 10A, Step 1: site-visit and customer-outreach tools for new,
tool-calling-capable AI Workforce employees.

get_available_slots is read-only (real availability, via
app.services.scheduling.appointment_service.AppointmentService - the
same rules engine the customer-widget booking flow and the dashboard
already use).

The other four tools - propose_visit, confirm_visit, create_follow_up,
draft_customer_message - never mutate a real Appointment/Booking and
never send a real customer communication. Each one only creates a
pending app.services.ai_workforce.approval_service.AIActionApproval
record describing the proposed action (see Phase 10A spec Step 6: the
approval primitive "must NOT automatically perform an action merely
because a record is approved", and must not yet be wired to real
booking mutation or external communication). Booking a real site visit
still goes through AppointmentService.book()/.confirm() exactly as it
already does today (dashboard actions, the customer widget's
save_lead_info/schedule_visit tool flow) - this module adds a *second*,
human-gated path for the new AI employees, not a replacement for those.

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
