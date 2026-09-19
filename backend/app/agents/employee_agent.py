"""Authenticated, persistent AI Employee for the agency dashboard.

This is the real execution path for the owner-facing chat: every message
goes through Planner -> ManagerAgent -> Employee(s) -> ToolRouter -> real
services (LLM + DB), and the Manager's synthesized reply is what gets
returned and saved - not a separate generic tool loop.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.agents.manager_agent import SPECIALIST_ORDER
from app.agents.orchestrator import AIOrchestrator
from app.agents.prompt_guard import AI_ACTION_LIMIT_MESSAGE, is_fallback_reply
from app.repositories.conversation_repository import (
    get_or_create_employee_conversation,
    load_history,
    save_message,
)
from app.services.ai_workforce.execution_service import AgentExecutionService
from app.services.billing.entitlement_service import EntitlementService


class EmployeeAgent:
    def __init__(self, db: Session):
        self.db = db

    def process(self, agency_id: str, conversation_id: Optional[str], message: str) -> dict:
        agency = self.db.query(models.Agency).filter(models.Agency.id == agency_id).first()
        if agency is None:
            raise ValueError("Agency not found")

        conversation = get_or_create_employee_conversation(self.db, agency.id, conversation_id=conversation_id)
        save_message(self.db, conversation.id, "user", message)

        # Same billing-phase rule as the customer-facing widget (see
        # services/shared/conversation_service.py): checked before any
        # LLM cost is incurred, degrades gracefully rather than erroring
        # (an agency user is on the other end of this chat, same as a
        # customer is on the other end of the widget), and records
        # nothing, since no AI action actually happened.
        allowed, _reason = EntitlementService(self.db).can_use_ai_action(agency)
        if not allowed:
            save_message(self.db, conversation.id, "assistant", AI_ACTION_LIMIT_MESSAGE)
            return {
                "conversation_id": conversation.id,
                "reply": AI_ACTION_LIMIT_MESSAGE,
                "intent": "general",
                "tool": None,
                "confidence": 0.0,
                "tool_result": None,
                "plan": None,
                "manager_result": {"final_reply": AI_ACTION_LIMIT_MESSAGE, "employee_results": {}, "memory": {"summary": None, "facts": []}},
            }

        history = load_history(self.db, conversation.id)

        orchestrator = AIOrchestrator(self.db, agency, conversation, lead=None)
        agent_context = orchestrator.before_llm(message, history)

        manager_result = agent_context["manager_result"]
        reply = manager_result.get("final_reply") or "Sorry, I couldn't process that just now."
        reply = orchestrator.after_llm(reply)

        plan = agent_context.get("plan")
        intent = getattr(plan, "intent", "general") if plan else "general"
        tools = getattr(plan, "tools", []) if plan else []
        confidence = getattr(plan, "confidence", 0.8) if plan else 0.8

        employee_results = manager_result.get("employee_results", {})
        tool_result = next(
            (res.get("tool_result") for res in employee_results.values() if res.get("tool_result")),
            None,
        )

        # One AI action per dashboard chat turn - but only record it here
        # if no real-estate specialist ran, since any of SPECIALIST_ORDER
        # already records its own AgentExecution row inside its own
        # tool-calling turn (app.agents.tool_calling_employee); recording
        # again here would double-count the exact same underlying LLM
        # call. This only covers the "legacy single-shot" employees
        # (receptionist/finance/marketing/support/analytics/sales/
        # manager-only replies), which have never recorded anything.
        if not any(name in SPECIALIST_ORDER for name in employee_results):
            AgentExecutionService(self.db).record(
                agency.id,
                employee="ai_manager",
                status=models.AgentExecutionStatus.failed if is_fallback_reply(reply) else models.AgentExecutionStatus.succeeded,
                conversation_id=conversation.id,
            )

        save_message(self.db, conversation.id, "assistant", reply)

        shared_memory = agent_context.get("shared_memory") or {}

        return {
            "conversation_id": conversation.id,
            "reply": reply,
            "intent": intent,
            "tool": tools[0] if tools else None,
            "confidence": confidence,
            "tool_result": tool_result,
            "plan": {
                "intent": plan.intent,
                "confidence": plan.confidence,
                "priority": plan.priority,
                "employees": plan.employees,
                "tools": plan.tools,
            }
            if plan
            else None,
            "manager_result": {
                "final_reply": manager_result.get("final_reply"),
                "employee_results": employee_results,
                "memory": {
                    "summary": shared_memory.get("summary"),
                    "facts": shared_memory.get("facts", []),
                },
            },
        }

    def history(self, agency_id: str, conversation_id: Optional[str] = None) -> dict:
        agency = self.db.query(models.Agency).filter(models.Agency.id == agency_id).first()
        if agency is None:
            raise ValueError("Agency not found")
        conversation = get_or_create_employee_conversation(self.db, agency.id, conversation_id=conversation_id)
        return {
            "conversation_id": conversation.id,
            "messages": load_history(self.db, conversation.id),
        }
