"""
Thin wrapper around any OpenAI-compatible chat completions API.

Works unmodified with OpenAI, Groq, Together, Fireworks, a self-hosted
vLLM/Ollama OpenAI-shim, or any other provider that speaks the same
/chat/completions schema. Swap providers by changing LLM_BASE_URL and
LLM_API_KEY in .env — nothing in this file or the rest of the app changes.
"""

import time

import openai
from openai import OpenAI

from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)

_client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


class LLMProviderError(Exception):
    """The LLM provider itself rejected or failed the request - as opposed
    to a bug in this app's own code. Wraps the specific `openai.APIError`
    subclass so every caller (llm_reply.py, conversation_service.py, the
    standalone extraction/quotation/campaign call sites) can react the same
    way without each needing to know the full set of provider exception
    classes. `reason` is a stable short code for logs/metrics; `user_message`
    is safe to show a customer (never includes provider-specific detail -
    org ids, billing links, raw error bodies - only in the log, via
    `original`)."""

    def __init__(self, reason: str, user_message: str, original: Exception):
        self.reason = reason
        self.user_message = user_message
        self.original = original
        super().__init__(f"{reason}: {original}")


def _classify_provider_error(exc: openai.APIError) -> tuple[str, str]:
    """openai.RateLimitError/AuthenticationError/APIConnectionError/etc. all
    inherit from openai.APIError - this only ever sees genuine provider-side
    failures, never a bug in this app's own request construction (a
    TypeError from bad kwargs, for instance, is a different exception type
    entirely and is not caught by the narrower `except openai.APIError` in
    chat_completion() below, so it still surfaces as itself)."""
    if isinstance(exc, openai.RateLimitError):
        return "rate_limited", (
            "Our AI assistant is getting a lot of requests right now. "
            "Please try again in a few minutes."
        )
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)):
        return "unavailable", "Our AI assistant is temporarily unavailable. Please try again shortly."
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        # A real customer/owner never needs to know this is a config
        # problem on our end - same safe message as "unavailable", but
        # logged under its own reason so an operator can tell the
        # difference (this needs a human to fix credentials, "unavailable"
        # usually resolves on its own).
        return "auth", "Our AI assistant is temporarily unavailable. Please try again shortly."
    if isinstance(exc, openai.BadRequestError):
        return "invalid_request", "Sorry, I couldn't process that request. Could you rephrase it?"
    return "unknown", "Sorry, I couldn't process that just now. Could you try again?"


def chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto"):
    """
    messages: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
    tools: OpenAI-style tool/function definitions (optional)
    Returns the raw completion message object (choices[0].message).

    Logs shape and timing only - never the actual message content, which
    would include system prompts and customer PII (see logging_config.py).

    Raises LLMProviderError (not the raw openai.* exception) when the
    provider itself is the cause of the failure, so every caller gets a
    classified reason and a safe, honest user-facing message instead of
    silently swallowing the real cause into one generic string regardless
    of what actually went wrong.
    """
    kwargs = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.4,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    start = time.perf_counter()
    try:
        response = _client.chat.completions.create(**kwargs)
    except openai.APIError as exc:
        reason, user_message = _classify_provider_error(exc)
        logger.exception("llm.call_failed", extra={"ctx": {
            "event": "llm.call_failed", "model": settings.llm_model,
            "message_count": len(messages), "tools_offered": bool(tools),
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            "success": False, "error_reason": reason,
        }})
        raise LLMProviderError(reason, user_message, exc) from exc

    message = response.choices[0].message
    logger.info("llm.call_completed", extra={"ctx": {
        "event": "llm.call_completed", "model": settings.llm_model,
        "message_count": len(messages), "tools_offered": bool(tools),
        "tool_calls_returned": bool(getattr(message, "tool_calls", None)),
        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        "success": True,
    }})
    return message
