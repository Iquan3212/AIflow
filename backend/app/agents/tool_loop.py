"""
Phase 10A: a small, generic bounded LLM tool-calling loop for new,
tool-calling-capable AI Workforce employees (see Registry.register_employee's
`tool_calling` flag and ToolRouter, which remains the actual permission
gate for every tool call this loop makes).

This generalizes the same bounded-round-robin shape already proven in
app.services.shared.conversation_service._run_tool_loop (real
chat_completion(tools=...) rounds, capped at MAX_TOOL_ROUNDS, then one
final no-tools synthesis call) behind a `call_tool` callback, instead of
being tied to that module's own ToolDispatcher/scheduling-tools registry.
The existing customer-conversation pipeline in conversation_service.py is
deliberately left untouched by this module - this is new, parallel
infrastructure for new employees, not a refactor of working, tested code.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable

from app.services.llm_client import chat_completion, LLMProviderError
from app.logging_config import get_logger

logger = get_logger(__name__)

MAX_TOOL_ROUNDS = 4

_FINAL_SYNTHESIS_INSTRUCTION = (
    "You must answer now in plain text for the customer/agency user. "
    "Do not request another tool call."
)


@dataclass
class ToolCallRecord:
    tool: str
    args: dict
    duration_ms: float
    ok: bool


@dataclass
class ToolLoopResult:
    reply: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    rounds_used: int = 0
    # "final_reply" | "max_rounds" | "provider_error"
    terminated_reason: str = "final_reply"


def run_bounded_tool_loop(
    messages: list[dict],
    tools: list[dict],
    call_tool: Callable[[str, dict], str],
    *,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> ToolLoopResult:
    """Drives `messages` through up to `max_rounds` of real LLM tool-calling.

    `call_tool(tool_name, args) -> str` executes exactly one tool call and
    must return a string (the tool's result, JSON-encoded or plain text) -
    callers wire this to ToolRouter.execute(...) so every call stays
    permission-gated exactly like the legacy single-shot employees. A
    `call_tool` exception is caught here (a broken tool must never crash
    the loop or the employee's turn) and reported to the model as a
    structured failure so it can recover or say so, rather than silently
    stalling.
    """
    tool_calls: list[ToolCallRecord] = []
    try:
        for round_num in range(max_rounds):
            msg = chat_completion(messages, tools=tools, tool_choice="auto")
            calls = getattr(msg, "tool_calls", None)

            if not calls:
                text = (msg.content or "").strip()
                return ToolLoopResult(
                    reply=text or "I don't have a response for that right now.",
                    tool_calls=tool_calls, rounds_used=round_num, terminated_reason="final_reply",
                )

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in calls
                ],
            })

            for tc in calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except json.JSONDecodeError:
                    args = {}

                start = time.perf_counter()
                ok = True
                try:
                    result = call_tool(tc.function.name, args)
                except Exception:
                    logger.exception("tool_loop.tool_call_failed", extra={"ctx": {
                        "event": "tool_loop.tool_call_failed", "tool": tc.function.name,
                    }})
                    ok = False
                    result = json.dumps({"success": False, "error": "tool_execution_failed"})
                duration_ms = round((time.perf_counter() - start) * 1000, 1)
                tool_calls.append(ToolCallRecord(tool=tc.function.name, args=args, duration_ms=duration_ms, ok=ok))
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        # Rounds exhausted: one final, tools-free synthesis call - never a
        # 5th tool round, so this can never recurse further no matter what
        # the model asks for.
        messages.append({"role": "system", "content": _FINAL_SYNTHESIS_INSTRUCTION})
        try:
            final = chat_completion(messages, tools=None, temperature=0)
            text = (final.content or "").strip()
        except LLMProviderError as exc:
            logger.warning("tool_loop.final_synthesis_failed", extra={"ctx": {
                "event": "tool_loop.final_synthesis_failed", "error_reason": exc.reason,
            }})
            text = ""

        return ToolLoopResult(
            reply=text or "I've gathered the information but need a moment - please ask again.",
            tool_calls=tool_calls, rounds_used=max_rounds, terminated_reason="max_rounds",
        )
    except LLMProviderError as exc:
        logger.warning("tool_loop.provider_error", extra={"ctx": {
            "event": "tool_loop.provider_error", "error_reason": exc.reason,
        }})
        return ToolLoopResult(reply=exc.user_message, tool_calls=tool_calls, terminated_reason="provider_error")
