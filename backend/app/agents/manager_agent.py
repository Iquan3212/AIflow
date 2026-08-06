from typing import Any, Dict, List

from app.agents.registry import Registry
from app.agents.memory import ConversationMemory


class ManagerAgent:
    """
    ManagerAgent: coordinates employees, delegates work, merges responses,
    resolves conflicts, and produces a unified context for the LLM.
    """

    def __init__(self, registry: Registry, memory: ConversationMemory):
        self.registry = registry
        self.memory = memory

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

            # Prefer analyze() if present, otherwise call handle()
            analyze = getattr(employee_instance, "analyze", None)
            handle = getattr(employee_instance, "handle", None)
            try:
                if callable(analyze):
                    result = analyze(message, history)
                elif callable(handle):
                    result = handle(message=message, history=history)
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
        - Prefer reply from employee associated with highest priority intent.
        - If multiple replies, then label sections by employee and deduplicate sentences.
        - Synthesize a manager summary line.
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

        # Deduplicate by sentence and build labeled sections
        seen = set()
        parts = []
        for name, txt in replies:
            sentences = [s.strip() for s in txt.split(".") if s.strip()]
            unique = []
            for s in sentences:
                if s not in seen:
                    seen.add(s)
                    unique.append(s)
            if unique:
                parts.append(f"{name.capitalize()} suggested: " + ". ".join(unique) + ".")

        # Manager synthesis: collect first line of each reply
        synth_lines = []
        for _, txt in replies:
            first_line = txt.split(".")[0]
            if first_line:
                synth_lines.append(first_line.strip())

        synthesis = " / ".join(synth_lines[:3])
        combined = "\n".join(parts)
        return f"{combined}\n\nManager synthesis: {synthesis}"

    def resolve_handoff(self, from_employee: str, to_employee: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a handoff payload from one employee to another.
        """
        return {
            "from": from_employee,
            "to": to_employee,
            "context": context,
        }