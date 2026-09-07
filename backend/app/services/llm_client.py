"""
Thin wrapper around any OpenAI-compatible chat completions API.

Works unmodified with OpenAI, Groq, Together, Fireworks, a self-hosted
vLLM/Ollama OpenAI-shim, or any other provider that speaks the same
/chat/completions schema. Swap providers by changing LLM_BASE_URL and
LLM_API_KEY in .env — nothing in this file or the rest of the app changes.
"""

import time

from openai import OpenAI

from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)

_client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto"):
    """
    messages: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
    tools: OpenAI-style tool/function definitions (optional)
    Returns the raw completion message object (choices[0].message).

    Logs shape and timing only - never the actual message content, which
    would include system prompts and customer PII (see logging_config.py).
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
    except Exception:
        logger.exception("llm.call_failed", extra={"ctx": {
            "event": "llm.call_failed", "model": settings.llm_model,
            "message_count": len(messages), "tools_offered": bool(tools),
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            "success": False,
        }})
        raise

    message = response.choices[0].message
    logger.info("llm.call_completed", extra={"ctx": {
        "event": "llm.call_completed", "model": settings.llm_model,
        "message_count": len(messages), "tools_offered": bool(tools),
        "tool_calls_returned": bool(getattr(message, "tool_calls", None)),
        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        "success": True,
    }})
    return message
