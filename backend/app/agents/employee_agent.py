"""Authenticated, persistent AI Employee for the business dashboard.

This is the real execution path for the owner-facing chat: every message
goes through Planner -> ManagerAgent -> Employee(s) -> ToolRouter -> real
services (LLM + DB), and the Manager's synthesized reply is what gets
returned and saved - not a separate generic tool loop.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.agents.orchestrator import AIOrchestrator
from app.repositories.conversation_repository import (
    get_or_create_employee_conversation,
    load_history,
    save_message,
)


class EmployeeAgent:
    def __init__(self, db: Session):
        self.db = db

    def process(self, business_id: str, conversation_id: Optional[str], message: str) -> dict:
        business = self.db.query(models.Business).filter(models.Business.id == business_id).first()
        if business is None:
            raise ValueError("Business not found")

        conversation = get_or_create_employee_conversation(self.db, business.id, conversation_id=conversation_id)
        save_message(self.db, conversation.id, "user", message)
        history = load_history(self.db, conversation.id)

        orchestrator = AIOrchestrator(self.db, business, conversation, lead=None)
        agent_context = orchestrator.before_llm(message, history)

        manager_result = agent_context["manager_result"]
        reply = manager_result.get("final_reply") or "Sorry, I couldn't process that just now."
        reply = orchestrator.after_llm(reply)

        save_message(self.db, conversation.id, "assistant", reply)

        plan = agent_context.get("plan")
        intent = getattr(plan, "intent", "general") if plan else "general"
        tools = getattr(plan, "tools", []) if plan else []
        confidence = getattr(plan, "confidence", 0.8) if plan else 0.8

        employee_results = manager_result.get("employee_results", {})
        tool_result = next(
            (res.get("tool_result") for res in employee_results.values() if res.get("tool_result")),
            None,
        )

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

    def history(self, business_id: str, conversation_id: Optional[str] = None) -> dict:
        business = self.db.query(models.Business).filter(models.Business.id == business_id).first()
        if business is None:
            raise ValueError("Business not found")
        conversation = get_or_create_employee_conversation(self.db, business.id, conversation_id=conversation_id)
        return {
            "conversation_id": conversation.id,
            "messages": load_history(self.db, conversation.id),
        }
