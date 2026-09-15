"""
Phase 10C, Agent #2: the Site Visit AI employee - registered under the
Registry key "site_visit" (no legacy employee uses this name, so no
collision/replacement risk, unlike Sales - see real_estate_sales_agent.py).

Every scheduling action goes through app.services.scheduling.
appointment_service.AppointmentService - the same rules engine the
customer-widget booking flow and the dashboard already use. This agent
never manipulates an Appointment ORM row directly; propose_visit/
confirm_visit/reschedule_visit/cancel_visit (its only granted mutation-
adjacent tools) all create a pending AIActionApproval instead of
mutating anything themselves - see app/tools/realestate_visit_followup_tools.py.
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.agents.llm_reply import knowledge_context_messages, retrieve_knowledge_context
from app.agents.tool_calling_employee import normalize_history_messages, run_tool_calling_employee_turn

EMPLOYEE_NAME = "site_visit"

GRANTED_TOOLS = [
    "get_lead", "get_property", "get_available_slots",
    "propose_visit", "confirm_visit", "reschedule_visit", "cancel_visit",
    "get_lead_appointments", "knowledge_search",
]


class SiteVisitAgent:
    """
    AI Workforce - Site Visit Employee

    Responsibilities (Phase 10C spec): inspect real appointment state
    for a lead/property, determine real availability, propose available
    slots, and assist with scheduling/rescheduling/cancellation/
    confirmation - always through AppointmentService, always
    approval-gated for anything that actually changes a real
    Appointment (proposing availability and drafting a scheduling
    recommendation are the only safe, un-gated actions).

    STATE RULE: the real AppointmentStatus is authoritative. This
    employee must never claim a visit is "confirmed" unless
    get_lead_appointments/confirm_visit's own tool result actually says
    so - scheduled != confirmed, cancelled != scheduled, completed !=
    pending.
    """

    def __init__(self, agency: Any, lead: Any = None):
        self.agency = agency
        self.lead = lead

    @property
    def system_prompt(self) -> str:
        name = getattr(self.agency, "name", None) or "the agency"
        return f"""You are the Site Visit AI for {name}.

ROLE

You help schedule, reschedule, cancel, and confirm real-estate site
visits, grounded entirely in real appointment data - never invented.

STATE RULE (critical)

The database's real AppointmentStatus is always authoritative. NEVER
say a site visit is "confirmed" unless a real tool result actually
returned status=confirmed. scheduled is NOT confirmed. cancelled is NOT
scheduled. completed is NOT pending. If you have not actually checked,
say you don't know rather than assuming.

HOW TO WORK

1. Call get_lead_appointments to see the lead's real, current
   appointment history and status before saying anything about it.
2. Call get_available_slots for a real, current day's open slots before
   proposing a time - never invent availability.
3. propose_visit/confirm_visit/reschedule_visit/cancel_visit each only
   PROPOSE the action (a human must approve before anything actually
   changes) - always tell the user this plainly, never imply the visit
   is already scheduled/confirmed/moved/cancelled just because you
   called one of these tools.

RULES

Never invent a lead's, property's, or appointment's details.

Proposing available slots or drafting a scheduling recommendation
needs no approval. Actually scheduling, confirming, rescheduling, or
cancelling a real visit always goes through the approval-gated tools
above - never claim it already happened.

Always remain concise and professional."""

    def respond(self, message: str, history: List[Any], tool_router: Optional[Any] = None) -> dict:
        if tool_router is None:
            return {"employee": EMPLOYEE_NAME, "intent": "site_visit", "reply": "", "tool_result": None, "error": "no_tool_router"}

        knowledge_context = retrieve_knowledge_context(tool_router, EMPLOYEE_NAME, message)
        extra_system_messages = knowledge_context_messages(knowledge_context)

        result = run_tool_calling_employee_turn(
            tool_router.registry, EMPLOYEE_NAME,
            db=tool_router.db, agency=tool_router.agency, conversation=tool_router.conversation, lead=tool_router.lead,
            system_prompt=self.system_prompt, history=normalize_history_messages(history), message=message,
            extra_system_messages=extra_system_messages,
        )

        return {
            "employee": EMPLOYEE_NAME,
            "intent": "site_visit",
            "reply": result.reply,
            "tool_result": {
                "ok": result.terminated_reason != "provider_error",
                "terminated_reason": result.terminated_reason,
                "tool_calls": [{"tool": tc.tool, "args": tc.args, "ok": tc.ok} for tc in result.tool_calls],
            },
        }
