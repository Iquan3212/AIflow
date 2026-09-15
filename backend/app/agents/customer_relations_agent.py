"""
Phase 10C, Agent #3: the Customer Relations AI employee - registered
under the Registry key "customer_relations" (no legacy employee uses
this name).

Read + draft oriented. draft_customer_message (create a draft - never
sent, no approval needed) and propose_send_customer_message (propose
ACTUALLY sending - always approval-gated) are both granted, matching
the Phase 10C rule: CREATE DRAFT automatically, SEND MESSAGE requires
approval. Sending itself, once approved, is executed through
GmailService.send() - the existing, authoritative Gmail send_mode/
GmailPendingAction control (see app.services.ai_workforce.
action_execution) - never bypassed, never a second messaging system.
No WhatsApp/Instagram automation here (Phase 11 scope).
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.agents.llm_reply import knowledge_context_messages, retrieve_knowledge_context
from app.agents.tool_calling_employee import normalize_history_messages, run_tool_calling_employee_turn

EMPLOYEE_NAME = "customer_relations"

GRANTED_TOOLS = [
    "get_lead", "get_property", "get_lead_appointments", "get_lead_bookings",
    "knowledge_search", "draft_customer_message", "propose_send_customer_message",
]


class CustomerRelationsAgent:
    """
    AI Workforce - Customer Relations Employee

    Responsibilities (Phase 10C spec): summarize the buyer relationship
    and lead history, identify unresolved questions/follow-up needs,
    summarize site visits and booking status, draft customer
    communications, and recommend the next interaction - primarily
    read + draft. Can propose (never itself perform) actually sending a
    message.
    """

    def __init__(self, agency: Any, lead: Any = None):
        self.agency = agency
        self.lead = lead

    @property
    def system_prompt(self) -> str:
        name = getattr(self.agency, "name", None) or "the agency"
        return f"""You are the Customer Relations AI for {name}.

ROLE

You summarize a real lead's relationship with the agency and help draft
- and, when appropriate, propose sending - customer communications.
Everything you say about this lead's history must come from a real
tool result, never invented.

HOW TO WORK

1. Call get_lead for the real, current CRM record.
2. Call get_lead_appointments and get_lead_bookings for the real
   site-visit and booking history - their DB status is authoritative:
   never claim a visit is confirmed/cancelled/completed or a booking
   exists/its status without checking these first.
3. Summarize what's actually there: unresolved questions, follow-up
   needs, and a recommended next interaction.
4. You may draft_customer_message freely (creates a draft only - never
   sent, no approval needed). If you determine an actual send is
   warranted, use propose_send_customer_message - this only creates a
   pending request for a human to approve; it never sends anything
   itself, and you must say so plainly.

RULES

Never invent a lead's history, a document's content, or claim a
message was sent - only draft_customer_message/propose_send_customer_message's
own tool result determines what actually happened, and neither of them
ever means a message left the building.

Always remain concise and professional."""

    def respond(self, message: str, history: List[Any], tool_router: Optional[Any] = None) -> dict:
        if tool_router is None:
            return {"employee": EMPLOYEE_NAME, "intent": "customer_relations", "reply": "", "tool_result": None, "error": "no_tool_router"}

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
            "intent": "customer_relations",
            "reply": result.reply,
            "tool_result": {
                "ok": result.terminated_reason != "provider_error",
                "terminated_reason": result.terminated_reason,
                "tool_calls": [{"tool": tc.tool, "args": tc.args, "ok": tc.ok} for tc in result.tool_calls],
            },
        }
