"""
Phase 10C, Agent #1: the real-estate-specialized Sales AI employee.

ARCHITECTURE DECISION - Option B (new, distinct registry key), not
Option A (specializing the existing "sales" key):

app/agents/sales_agent.py's SalesAgent is registered under the Registry
key "sales" and is reachable by Planner's existing "sales" intent
(keywords: price/quotation/quote/cost/buy/purchase/discount/pricing/
create-a-lead/...- see planner.py). Its system prompt is deliberately
generic - "You are the Sales AI for {agency.name}... Only recommend
services listed [in chatbot_config.services]" - because AIFlow serves
ANY business type (salons, restaurants, clinics, etc.), not only real
estate agencies; real estate is this product's current strategic focus,
not its only supported vertical.

If this new employee were registered under the SAME key "sales"
(literally replacing SalesAgent in the Registry dict), every non-real-
estate agency - and every real-estate agency's own generic pricing/
"create a lead" questions - would silently lose that generic behavior
and get a real-estate-only prompt/toolset instead. That is exactly the
"accidentally replace or break the legacy generic employee" the Phase
10C spec warns against.

So this employee is registered under a NEW key, "real_estate_sales" -
Planner routes to it only via a NEW, distinct intent (keywords about a
specific lead's next-best-action/follow-up/stalled-lead status - see
planner.py's "real_estate_sales" intent), never colliding with the
existing "sales" intent/keywords/employee. No duplicate or conflicting
execution path: the legacy single-shot "sales" employee is untouched
(same tools, same behavior, same registry key), and this is an
entirely separate, additive, tool-calling employee.
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.agents.llm_reply import knowledge_context_messages, retrieve_knowledge_context
from app.agents.tool_calling_employee import normalize_history_messages, run_tool_calling_employee_turn

EMPLOYEE_NAME = "real_estate_sales"

GRANTED_TOOLS = [
    "get_lead", "get_property", "search_properties", "get_project",
    "get_lead_appointments", "get_lead_bookings", "update_lead_qualification",
    "draft_customer_message", "knowledge_search",
]


class RealEstateSalesAgent:
    """
    AI Workforce - Real Estate Sales Employee

    Responsibilities (Phase 10C spec): inspect a lead, its requirements,
    the relevant property/project, its site-visit/booking history, and
    its current stage - then recommend the next best action (contact
    buyer, send follow-up, schedule site visit, re-engage after visit,
    recommend an alternate property, escalate, or mark lost) and
    optionally draft a follow-up message. Never invents customer
    information. Cannot mutate booking/appointment state, cannot send a
    message, cannot propose scheduling a visit itself - those stay with
    Site Visit/Customer Relations (this agent may only draft, and may
    update safe qualification fields via update_lead_qualification).
    """

    def __init__(self, agency: Any, lead: Any = None):
        self.agency = agency
        self.lead = lead

    @property
    def system_prompt(self) -> str:
        name = getattr(self.agency, "name", None) or "the agency"
        return f"""You are the Real Estate Sales AI for {name}.

ROLE

You help move a real, specific lead toward a sale by recommending the
next best action, grounded entirely in real data you retrieve via
tools - never invented.

HOW TO WORK

1. Call get_lead for the lead's real, current CRM record (status,
   qualification_score/notes, contact info, stated requirement).
2. If a property/project is relevant, call get_property/search_properties/
   get_project - never assume price, availability, or specs.
3. Call get_lead_appointments and get_lead_bookings to see the real
   site-visit and booking history - the DB status is authoritative:
   never claim a visit is confirmed/completed or a booking exists
   unless these tools actually say so.
4. Recommend ONE next best action, chosen from real signals: contact
   buyer, send a follow-up, schedule a site visit, re-engage after a
   completed visit, recommend an alternate property (only if you found
   one via search_properties), escalate to a human, or mark the lead as
   lost if genuinely stalled with no real signal of continued interest.
5. You may update qualification_score/qualification_notes/status via
   update_lead_qualification (safe internal CRM fields), and you may
   draft a follow-up message via draft_customer_message (never sent by
   this tool - a human reviews it).

RULES

Never invent a lead's name, phone, email, budget, requirement, or
interaction history not actually returned by a tool.

You cannot schedule, confirm, reschedule, or cancel a site visit, and
you cannot send a message or create/confirm a booking - those actions
belong to other employees or require a human. If one of those is the
right next step, RECOMMEND it, do not attempt to perform it.

Always remain concise and professional."""

    def respond(self, message: str, history: List[Any], tool_router: Optional[Any] = None) -> dict:
        if tool_router is None:
            return {"employee": EMPLOYEE_NAME, "intent": "real_estate_sales", "reply": "", "tool_result": None, "error": "no_tool_router"}

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
            "intent": "real_estate_sales",
            "reply": result.reply,
            "tool_result": {
                "ok": result.terminated_reason != "provider_error",
                "terminated_reason": result.terminated_reason,
                "tool_calls": [{"tool": tc.tool, "args": tc.args, "ok": tc.ok} for tc in result.tool_calls],
            },
        }
