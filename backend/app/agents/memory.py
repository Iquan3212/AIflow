from typing import Any, Dict, List
import re


class ConversationMemory:
    """
    Shared conversation memory for the AI workforce.

    Provides:
    - summarize_messages(history)
    - important_facts(history)
    - recent_messages(history)
    - customer_profile(history)
    - shared_context(history) -> aggregated structure
    """

    def __init__(self, summary_max_messages: int = 20):
        self.summary_max_messages = summary_max_messages

    def summarize_messages(self, history: List[Any]) -> str:
        if not history:
            return "No previous conversation."

        recent = history[-self.summary_max_messages :]
        lines = []
        for item in recent:
            if isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")
            else:
                role = getattr(item, "role", "user")
                content = getattr(item, "content", "")
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _content_of(self, item: Any) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return item.get("content", "") or ""
        return getattr(item, "content", "") or ""

    def important_facts(self, history: List[Any]) -> List[str]:
        if not history:
            return []
        text = " ".join(self._content_of(m) for m in history[-50:])
        facts = []
        # emails
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        for e in set(emails):
            facts.append(f"email:{e}")
        # phones (simple heuristic)
        phones = re.findall(r"\+?\d[\d\-\s]{6,}\d", text)
        for p in set(phones):
            facts.append(f"phone:{p}")
        # names: look for "my name is X" / "i am X"
        m = re.search(r"\b(?:my name is|i am|this is)\s+([A-Z][a-zA-Z]{1,20})", text)
        if m:
            facts.append(f"name:{m.group(1)}")
        return facts

    def customer_profile(self, history: List[Any]) -> Dict[str, Any]:
        profile: Dict[str, Any] = {}
        # sample heuristics
        for item in history[-40:]:
            content = self._content_of(item)
            if "company" in content.lower():
                profile["mentioned_company"] = True
            if "address" in content.lower() or "located in" in content.lower():
                profile["has_address"] = True
        return profile

    def recent_messages(self, history: List[Any], limit: int = 10) -> List[Any]:
        return list(history[-limit:]) if history else []

    def shared_context(self, history: List[Any]) -> Dict[str, Any]:
        summary = self.summarize_messages(history)
        facts = self.important_facts(history)
        profile = self.customer_profile(history)
        recent = self.recent_messages(history)
        return {
            "summary": summary,
            "facts": facts,
            "recent_messages": recent,
            "profile": profile,
            "long_term_hooks": [],  # future integration points for long-term memory stores
        }