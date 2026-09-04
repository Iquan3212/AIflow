"""Shared helper so every AI Workforce employee grounds its reply in its own
system prompt, the real conversation history, and any real tool result -
instead of returning bare keyword-classification metadata."""

from typing import Any, List, Optional

from app.services.llm_client import chat_completion

# Matches ConversationMemory.summary_max_messages - the two systems should
# agree on how much of a conversation counts as "recent", otherwise memory
# extraction (facts/summary) and the raw history the model actually sees can
# disagree about what's still in scope.
MAX_HISTORY_MESSAGES = 20


def _message_role_content(item: Any) -> tuple[Optional[str], Optional[str]]:
    if isinstance(item, dict):
        return item.get("role"), item.get("content")
    return getattr(item, "role", None), getattr(item, "content", None)


def facts_context(analysis: Optional[dict]) -> Optional[str]:
    """Turns the facts ConversationMemory already extracts (name/phone/email
    mentioned earlier) into a grounding line for the prompt. Without this,
    identity was only ever surfaced for display (the Manager UI's Memory
    panel) and never actually fed back into generation - the model had to
    re-notice a name purely from scanning raw history, which is more prone
    to it re-asking for closer-to-page-boundary conversations to be lost."""
    if not analysis:
        return None
    facts = (analysis.get("memory") or {}).get("facts") or []
    if not facts:
        return None
    return (
        "Known facts already established earlier in this conversation - do "
        "not ask for these again unless the customer contradicts them: "
        + "; ".join(facts)
    )


def _format_for_prompt(value: Any, indent: int = 0) -> str:
    """Renders a tool result as clean, human-readable text instead of raw
    JSON - so if a weaker model's reply leans on this context too literally,
    what leaks through reads as prose, not `["a", "b"]`/escaped-quote syntax."""
    pad = "  " * indent
    if isinstance(value, dict):
        lines = []
        for key, val in value.items():
            label = str(key).replace("_", " ")
            if isinstance(val, (dict, list)) and val:
                lines.append(f"{pad}{label}:")
                lines.append(_format_for_prompt(val, indent + 1))
            else:
                lines.append(f"{pad}{label}: {_format_for_prompt(val, 0) if not isinstance(val, (dict, list)) else '(none)'}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}(none)"
        return "\n".join(f"{pad}- {_format_for_prompt(item, 0)}" for item in value)
    if value is None:
        return "(not set)"
    return str(value)


def generate_employee_reply(
    employee_name: str,
    system_prompt: str,
    message: str,
    history: Optional[List[Any]] = None,
    tool_result: Optional[dict] = None,
    extra_context: Optional[str] = None,
) -> str:
    """Runs one real LLM completion grounded in `system_prompt`, the recent
    conversation, and (if present) the outcome of the tool this employee just
    ran, so the reply reflects what actually happened rather than a template."""
    messages = [{"role": "system", "content": system_prompt}]

    for item in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role, content = _message_role_content(item)
        if not content:
            continue
        messages.append({"role": role if role in ("user", "assistant") else "user", "content": content})

    if not messages[1:] or messages[-1].get("content") != message:
        messages.append({"role": "user", "content": message})

    if extra_context:
        messages.append({"role": "system", "content": extra_context})

    if tool_result is not None:
        messages.append({
            "role": "system",
            "content": (
                "Result of the action you just took (ground your reply in this; "
                "do not mention tool names, field names, or any raw data "
                "structure to the customer - phrase it as natural language):\n"
                + _format_for_prompt(tool_result)
            ),
        })

    reply = ""
    for attempt in range(2):  # some models occasionally emit a spurious tool-call
        try:                  # even with no tools offered; one retry clears it.
            completion = chat_completion(messages)
            reply = (completion.content or "").strip()
            break
        except Exception as exc:
            print(f"[{employee_name}:llm-error attempt={attempt}] {exc}")

    return reply or "Sorry, I couldn't process that just now. Could you try again?"
