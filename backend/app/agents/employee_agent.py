"""Authenticated, persistent AI Employee for the business dashboard.

EmployeeAgent remains the chat entrypoint only. Business coordination moved into AIOrchestrator/ManagerAgent.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.agents.dashboard_tools import DashboardToolDispatcher, dashboard_tool_definitions
from app.agents.orchestrator import AIOrchestrator
from app.repositories.conversation_repository import (
    get_or_create_employee_conversation,
    load_history,
    save_message,
)
from app.services.shared.conversation_service import _run_tool_loop
from app.services.prompt_builder import build_dashboard_prompt


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

        # Build the system prompt using the existing helper to preserve behavior
        system_prompt = build_dashboard_prompt(
            business=business,
            config=business.chatbot_config,
            memory=agent_context.get("memory"),
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": item.role, "content": item.content} for item in history)

        dispatcher = DashboardToolDispatcher(self.db, business)
        try:
            reply = _run_tool_loop(messages, dashboard_tool_definitions(), dispatcher)
        except Exception as exc:
            # Provider outage - respond gracefully while preserving conversation
            print(f"[employee-agent:error] {exc}")
            reply = "I couldn't reach the AI service just now. Please try again in a moment."

        reply = orchestrator.after_llm(reply)
        save_message(self.db, conversation.id, "assistant", reply)

        plan = agent_context.get("plan")
        # Normalize plan for compatibility
        intent = getattr(plan, "intent", "general") if plan else "general"
        tools = getattr(plan, "tools", []) if plan else []
        confidence = getattr(plan, "confidence", 0.8) if plan else 0.8

        return {
            "conversation_id": conversation.id,
            "reply": reply,
            "intent": intent,
            "tool": tools[0] if tools else None,
            "confidence": confidence,
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