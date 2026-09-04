"""Shared helper so every AI Workforce employee grounds its reply in its own
system prompt, the real conversation history, and any real tool result -
instead of returning bare keyword-classification metadata."""

import json
from typing import Any, List, Optional

from app.services.llm_client import chat_completion

MAX_HISTORY_MESSAGES = 10


def _message_role_content(item: Any) -> tuple[Optional[str], Optional[str]]:
    if isinstance(item, dict):
        return item.get("role"), item.get("content")
    return getattr(item, "role", None), getattr(item, "content", None)


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

    if tool_result is not None:
        messages.append({
            "role": "system",
            "content": (
                "Result of the action you just took (ground your reply in this; "
                "do not mention tool names or internal fields to the customer): "
                + json.dumps(tool_result, default=str)
            ),
        })

    if extra_context:
        messages.append({"role": "system", "content": extra_context})

    reply = ""
    for attempt in range(2):  # some models occasionally emit a spurious tool-call
        try:                  # even with no tools offered; one retry clears it.
            completion = chat_completion(messages)
            reply = (completion.content or "").strip()
            break
        except Exception as exc:
            print(f"[{employee_name}:llm-error attempt={attempt}] {exc}")

    return reply or "Sorry, I couldn't process that just now. Could you try again?"
