from typing import Any, Dict, List, Optional

from app.agents.llm_reply import generate_employee_reply
from app.agents.memory import ConversationMemory
from app.agents.registry import Registry


class ManagerAgent:
    """
    ManagerAgent: coordinates employees, delegates work, merges responses,
    resolves conflicts, and produces a unified context for the LLM.
    """

    def __init__(self, registry: Registry, memory: ConversationMemory, business: Any = None, tool_router: Any = None):
        self.registry = registry
        self.memory = memory
        self.business = business
        self.tool_router = tool_router

    @property
    def system_prompt(self) -> str:
        name = getattr(self.business, "name", None) or "the business"
        return f"""You are the Manager AI for {name}.

You coordinate a workforce of AI specialists: Sales, Receptionist, Support,
Finance, Marketing, and Analytics.

Answer general questions helpfully and concisely. Never invent business
facts, prices, or appointment slots yourself - that work belongs to the
specialist employees."""

    def respond(self, message: str, history: List[Any], tool_router: Optional[Any] = None) -> Dict[str, Any]:
        """The Manager's own reply for general chat that no specialist
        intent was detected for."""
        reply = generate_employee_reply("manager", self.system_prompt, message, history)
        return {"employee": "manager", "intent": "general", "reply": reply, "tool_result": None}

    def delegate(self, plan: Any, message: str, history: List[Any]) -> Dict[str, Any]:
        """
        Delegate to one or more employees indicated in plan.employees.
        Returns a unified structure containing employee_results, final_reply, unified_context.
        """
        employee_results: Dict[str, Dict[str, Any]] = {}

        for emp in getattr(plan, "employees", []) or ["manager"]:
            employee_instance = self.registry.get_employee(emp)
            if employee_instance is None:
                employee_results[emp] = {"reply": "", "tool_result": None, "error": "employee_not_registered"}
                continue

            # Prefer respond() (real LLM reply + real tool execution), then
            # legacy analyze()/handle() for any employee that hasn't been
            # upgraded yet.
            respond_fn = getattr(employee_instance, "respond", None)
            analyze_fn = getattr(employee_instance, "analyze", None)
            handle_fn = getattr(employee_instance, "handle", None)
            try:
                if callable(respond_fn):
                    result = respond_fn(message, history, self.tool_router)
                elif callable(analyze_fn):
                    result = analyze_fn(message, history)
                elif callable(handle_fn):
                    result = handle_fn(message=message, history=history)
                else:
                    result = {"reply": "", "tool_result": None}
            except Exception as exc:
                result = {"reply": "", "tool_result": None, "error": str(exc)}

            # Normalize result
            if not isinstance(result, dict):
                result = {"reply": str(result), "tool_result": None}

            if "reply" not in result:
                result.setdefault("reply", "")
            if "tool_result" not in result:
                result.setdefault("tool_result", None)

            employee_results[emp] = result

        final_reply = self._merge_replies(plan, employee_results, history)
        shared = self.memory.shared_context(history)

        unified_context = {
            "plan": plan,
            "shared_memory": shared,
            "employee_results": employee_results,
            "final_reply": final_reply,
        }

        return {
            "employee_results": employee_results,
            "final_reply": final_reply,
            "unified_context": unified_context,
        }

    def _merge_replies(self, plan: Any, employee_results: Dict[str, Dict[str, Any]], history: List[Any]) -> str:
        """
        Merge strategy:
        - Single employee: return its reply as-is.
        - Multiple employees: label each reply by employee so a multi-intent
          request (e.g. "create a lead and book an appointment") reads as one
          unified answer instead of losing either half.
        """
        replies = []
        for name, res in employee_results.items():
            txt = (res.get("reply") or "").strip()
            if txt:
                replies.append((name, txt))

        if not replies:
            return ""

        if len(replies) == 1:
            return replies[0][1]

        parts = [f"{name.capitalize()}: {txt}" for name, txt in replies]
        return "\n\n".join(parts)

    def resolve_handoff(self, from_employee: str, to_employee: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a handoff payload from one employee to another.
        """
        return {
            "from": from_employee,
            "to": to_employee,
            "context": context,
        }
