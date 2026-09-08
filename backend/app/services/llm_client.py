"""
Thin, provider-independent facade every caller in the app already uses:

    chat_completion(messages, tools=None, tool_choice="auto") -> ChatResult

raising LLMProviderError (never a provider SDK's own exception type) on
failure. The actual provider - Groq, Gemini, OpenRouter, or a local Ollama
server - is selected once, at import time, by LLM_PROVIDER (see
app/services/llm/factory.py). No caller needs to change to add or swap
providers: ManagerAgent, the employee agents, llm_reply.py, and the tools
all depend on this module's shape, never on a specific provider's SDK.

Optional single-attempt fallback: if LLM_FALLBACK_PROVIDER names a second
provider, a transient failure on the primary (rate limit/timeout/
unavailable/provider_error only - never an invalid request, an auth
problem, a prompt-injection refusal, or a tool/business-rule failure, none
of which are provider failures in the first place) retries once against
it. Disabled by default; never recurses - the fallback attempt's own
failure always propagates rather than trying a third provider.
"""

import time

from app.config import get_settings
from app.logging_config import get_logger
from app.services.llm.base import LLMProviderError, FALLBACK_ELIGIBLE_REASONS
from app.services.llm.factory import create_llm_provider

settings = get_settings()
logger = get_logger(__name__)

# Shared safety instruction for any caller running a completion with no
# `tools` offered, specifically because real tool execution already
# happened earlier (through ToolRouter or ToolDispatcher) and this call is
# only meant to phrase the final natural-language reply. No `tools` are
# passed in that shape of call, so it has no function-calling ability by
# request shape alone - but some tool-trained models (observed: Groq's
# openai/gpt-oss-20b) can still emit a tool-call-shaped generation anyway,
# which the provider then rejects since none were declared. Provider- and
# tool-agnostic (never names a specific tool) - used by both
# app/agents/llm_reply.py (the Manager/employee dashboard path) and
# app/services/shared/conversation_service.py's own post-tool-loop final
# call, never by any call site that genuinely offers `tools`.
NO_TOOL_CALL_INSTRUCTION = (
    "This is a final natural-language reply, not a tool-use step. Respond "
    "with plain conversational text only. Do not call, invoke, or emit a "
    "function/tool call in any form - no JSON, no code block, no "
    "structured call syntax - even if one seems relevant; instead describe "
    "the outcome in your own words using only the information already "
    "given to you above."
)

# Shared, tool-agnostic heuristic for "this text claims a capability isn't
# available" - used in three places that all need the SAME definition to
# stay consistent: llm_reply.py's synthesis retry backstop (discard a
# reply that contradicts a real, successful tool result this turn),
# llm_reply.py's history replay (never replay a past turn's stale denial
# as if it were still true), and manager_agent.py's multi-employee merge
# (a specialist with nothing to contribute must not have its blanket
# denial contaminate a sibling employee's real, successful result in the
# same reply). Never Gmail-specific - a plain phrase match, not an LLM
# call, so it costs nothing and never needs a specific tool's name.
CAPABILITY_DENIAL_PHRASES = (
    "don't have access", "do not have access",
    "no access to", "don't have any access", "do not have any access",
    "can't access", "cannot access", "not able to access",
)


def denies_capability(text: str) -> bool:
    # Confirmed live: real model output typesets "don't"/"can't" with a
    # typographic/curly apostrophe (U+2019, "'") far more often than a
    # straight ASCII one (U+0027, used in CAPABILITY_DENIAL_PHRASES above,
    # since that's what a Python source literal naturally contains) - this
    # silently defeated every single use of this check (the synthesis
    # backstop below, history replay, and manager_agent.py's merge
    # stripping all never actually matched a real denial once it used a
    # curly apostrophe, which is the model's default style). Normalizing
    # to a straight apostrophe before matching, rather than adding curly
    # variants to the phrase list, since the SAME real-text risk applies
    # to any future phrase added here too.
    lowered = (text or "").replace("’", "'").lower()
    return any(phrase in lowered for phrase in CAPABILITY_DENIAL_PHRASES)


def format_tool_result_for_prompt(value, indent: int = 0) -> str:
    """Renders any tool result (dict/list/scalar) as clean, human-readable
    text instead of raw JSON. Shared by llm_reply.py (grounding the LLM's
    own synthesis) and, when synthesis itself fails entirely, as the basis
    for a deterministic, code-generated fallback reply - never invents
    data, only reformats whatever the tool actually returned."""
    pad = "  " * indent
    if isinstance(value, dict):
        lines = []
        for key, val in value.items():
            label = str(key).replace("_", " ")
            if isinstance(val, (dict, list)) and val:
                lines.append(f"{pad}{label}:")
                lines.append(format_tool_result_for_prompt(val, indent + 1))
            else:
                lines.append(f"{pad}{label}: {format_tool_result_for_prompt(val, 0) if not isinstance(val, (dict, list)) else '(none)'}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}(none)"
        return "\n".join(f"{pad}- {format_tool_result_for_prompt(item, 0)}" for item in value)
    if value is None:
        return "(not set)"
    return str(value)

# LLMProviderError is imported (not redefined) above, so
# `from app.services.llm_client import chat_completion, LLMProviderError`
# (every existing call site) keeps working unchanged.

_provider = create_llm_provider(settings)

_fallback_name = (settings.llm_fallback_provider or "").strip().lower()
_fallback_provider = None
if _fallback_name and _fallback_name != "none":
    if _fallback_name == (settings.llm_provider or "groq").strip().lower():
        logger.warning("llm.fallback_same_as_primary", extra={"ctx": {
            "event": "llm.fallback_same_as_primary", "provider": _fallback_name,
        }})
    else:
        _fallback_provider = create_llm_provider(settings, provider_name=_fallback_name)


def chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto", temperature: float = 0.4):
    """
    messages: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
    tools: OpenAI-style tool/function definitions (optional)
    Returns a ChatResult (app.services.llm.base) - `.content` and, when the
    model made one, `.tool_calls` (each with `.id`/`.function.name`/
    `.function.arguments`).

    Logs shape and timing only - never the actual message content, which
    would include system prompts and customer PII (see logging_config.py).
    """
    start = time.perf_counter()
    try:
        result = _provider.chat(messages, tools=tools, tool_choice=tool_choice, temperature=temperature)
    except LLMProviderError as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.exception("llm.call_failed", extra={"ctx": {
            "event": "llm.call_failed", "provider": _provider.name, "model": _provider.model_name(),
            "message_count": len(messages), "tools_offered": bool(tools),
            "duration_ms": duration_ms, "success": False, "error_reason": exc.reason,
        }})

        if _fallback_provider is None or exc.reason not in FALLBACK_ELIGIBLE_REASONS:
            raise

        logger.warning("llm.fallback_triggered", extra={"ctx": {
            "event": "llm.fallback_triggered", "from_provider": _provider.name,
            "to_provider": _fallback_provider.name, "error_reason": exc.reason,
        }})
        fb_start = time.perf_counter()
        try:
            # Exactly one fallback attempt - deliberately not wrapped in
            # this same try/except, so a second failure here always
            # propagates rather than ever trying a third provider.
            result = _fallback_provider.chat(messages, tools=tools, tool_choice=tool_choice, temperature=temperature)
        except LLMProviderError as fb_exc:
            logger.exception("llm.fallback_failed", extra={"ctx": {
                "event": "llm.fallback_failed", "provider": _fallback_provider.name,
                "duration_ms": round((time.perf_counter() - fb_start) * 1000, 1),
                "success": False, "error_reason": fb_exc.reason,
            }})
            raise

        logger.info("llm.call_completed", extra={"ctx": {
            "event": "llm.call_completed", "provider": _fallback_provider.name,
            "model": _fallback_provider.model_name(), "message_count": len(messages),
            "tools_offered": bool(tools), "tool_calls_returned": bool(result.tool_calls),
            "duration_ms": round((time.perf_counter() - fb_start) * 1000, 1),
            "success": True, "via_fallback": True,
        }})
        return result

    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info("llm.call_completed", extra={"ctx": {
        "event": "llm.call_completed", "provider": _provider.name, "model": _provider.model_name(),
        "message_count": len(messages), "tools_offered": bool(tools),
        "tool_calls_returned": bool(result.tool_calls),
        "duration_ms": duration_ms, "success": True,
    }})
    return result


def get_llm_status() -> dict:
    """Safe status info for an operator - provider + model names only,
    never a key or any other credential. See routers/employee.py's
    GET /manager/status."""
    return {
        "provider": _provider.name,
        "model": _provider.model_name(),
        "fallback_provider": _fallback_provider.name if _fallback_provider else None,
    }
