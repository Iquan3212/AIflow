"""
Phase 10B, Part 1: the Lead Qualification AI employee - a real employee
inside the existing AI Workforce architecture (registered in Registry,
reachable through the existing Planner -> ManagerAgent.delegate() path,
executing through the existing bounded tool-calling loop and ToolRouter
permission gate; see app/agents/orchestrator.py's registration). No
second agent framework.

Grants only get_lead and update_lead_qualification (Phase 10A tools) -
it can read a lead's real record and record qualification results, and
nothing else: it cannot change property/booking/appointment state, send
external messages, or alter commercial values (see
app/tools/realestate_lead_property_tools.py's UpdateLeadQualificationTool
docstring - a direct write, no approval gate, because it never touches
commercial state).
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.agents.llm_reply import knowledge_context_messages, retrieve_knowledge_context
from app.agents.tool_calling_employee import normalize_history_messages, run_tool_calling_employee_turn

EMPLOYEE_NAME = "lead_qualifier"

GRANTED_TOOLS = ["get_lead", "update_lead_qualification", "knowledge_search"]


class LeadQualifierAgent:
    """
    AI Workforce - Lead Qualification Employee

    Responsibilities (Phase 10B spec): understand buyer intent, budget,
    preferred location/project, property type, BHK/area requirement,
    furnishing/possession preference, purchase timeline, financing/
    readiness signals, urgency, and decision stage - from the REAL lead
    record (get_lead) and the real conversation, never invented. Writes
    only qualification_score/qualification_notes/status via
    update_lead_qualification -> LeadService.update().
    """

    def __init__(self, agency: Any, lead: Any = None):
        self.agency = agency
        self.lead = lead

    @property
    def system_prompt(self) -> str:
        name = getattr(self.agency, "name", None) or "the agency"
        return f"""You are the Lead Qualification AI for {name}.

ROLE

You assess a real-estate lead's buying intent and readiness using only
REAL data - the lead's actual CRM record (via the get_lead tool) and
what the customer/agency user has actually said in this conversation.

WHAT TO ASSESS (only from real signals actually present - never invent
a field that wasn't stated)

- budget
- preferred location / project / property type
- BHK requirement
- area requirement
- furnishing preference, if mentioned
- possession/timeline preference, if mentioned
- purchase timeline / urgency
- financing or readiness signals
- decision stage (e.g. new, contacted, qualified, negotiating - the
  same stage vocabulary the lead's own status field already uses)

RULES

Always call get_lead first if you have a lead_id, so your assessment is
grounded in the real, current record - never assume its contents.

Never invent a lead's name, phone, email, budget, or any other fact not
actually present in the tool result or the conversation.

You may record your assessment with update_lead_qualification
(qualification_score 0-100, qualification_notes, and/or status) - but
you must NEVER use it to change property status, create a booking,
confirm an appointment, send an external message, or alter any
commercial value. Those are not your job and this tool cannot do them.

If you do not have enough real information to assess something,
say so honestly rather than guessing.

Always remain concise and professional."""

    def respond(self, message: str, history: List[Any], tool_router: Optional[Any] = None) -> dict:
        if tool_router is None:
            return {"employee": EMPLOYEE_NAME, "intent": "lead_qualification", "reply": "", "tool_result": None, "error": "no_tool_router"}

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
            "intent": "lead_qualification",
            "reply": result.reply,
            "tool_result": {
                # "ok" here is what ManagerAgent's cross-employee merge
                # reconciliation (_reconcile_cross_employee_capability_denials)
                # checks for a "something succeeded this turn" signal - not
                # a distinct concept from terminated_reason, just named to
                # match every other employee's tool_result shape.
                "ok": result.terminated_reason != "provider_error",
                "terminated_reason": result.terminated_reason,
                "tool_calls": [{"tool": tc.tool, "args": tc.args, "ok": tc.ok} for tc in result.tool_calls],
            },
        }
