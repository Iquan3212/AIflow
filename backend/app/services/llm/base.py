"""
Canonical, provider-independent LLM contract. Every provider adapter
(openai_compatible.py - Groq/OpenRouter/Ollama; gemini_provider.py)
implements LLMProvider and only ever returns/raises the types defined
here - nothing above llm_client.py (ManagerAgent, employees, tools,
llm_reply.py) ever sees a provider SDK's own request/response/exception
type. This is what makes the provider swappable through configuration
alone: every caller depends on this module's shapes, never on `openai.*`
or `google.genai.*` directly.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

# ---- canonical error categories --------------------------------------------
# Every adapter maps its own provider's exceptions onto exactly one of
# these - see each adapter's _classify()/_classify_api_error().

RATE_LIMITED = "rate_limited"
AUTHENTICATION_ERROR = "authentication_error"
TIMEOUT = "timeout"
UNAVAILABLE = "unavailable"
INVALID_REQUEST = "invalid_request"
PROVIDER_ERROR = "provider_error"

ALL_REASONS = frozenset({
    RATE_LIMITED, AUTHENTICATION_ERROR, TIMEOUT, UNAVAILABLE, INVALID_REQUEST, PROVIDER_ERROR,
})

# Only these are worth retrying against a *different* provider (see
# llm_client.py's fallback logic). A request rejected as malformed
# (invalid_request) or refused by our own code before it ever reaches a
# provider would fail identically on any other provider too - falling back
# would just waste a second call for a second, identical failure. Not
# used for prompt-injection refusals or agency/tool-rule failures at
# all: those never raise LLMProviderError in the first place, since they
# are not provider failures - see prompt_guard.py and ToolRouter.
FALLBACK_ELIGIBLE_REASONS = frozenset({RATE_LIMITED, TIMEOUT, UNAVAILABLE, PROVIDER_ERROR})

# ---- canonical customer-safe failure messages ------------------------------
# Shared by every adapter (openai_compatible.py and gemini_provider.py used
# to each define their own identical copies of these four strings - single
# source of truth now). Also used by prompt_guard.py to recognize a reply as
# "this app's own failure text", never real assistant content - see
# is_fallback_reply() - so a transient provider hiccup doesn't get replayed
# to the model as if it were prior conversation history.
RATE_LIMIT_MESSAGE = "Our AI assistant is getting a lot of requests right now. Please try again in a few minutes."
UNAVAILABLE_MESSAGE = "Our AI assistant is temporarily unavailable. Please try again shortly."
INVALID_REQUEST_MESSAGE = "Sorry, I couldn't process that request. Could you rephrase it?"
PROVIDER_ERROR_MESSAGE = "Sorry, I couldn't process that just now. Could you try again?"


class LLMProviderError(Exception):
    """The LLM provider itself rejected or failed the request - as opposed
    to a bug in this app's own code. `reason` is one of the categories
    above (stable, used for logs/metrics and fallback eligibility);
    `user_message` is safe to show a customer (never provider-specific
    detail - org ids, billing links, raw error bodies - those stay only in
    `original`, which is logged, never returned to a client)."""

    def __init__(self, reason: str, user_message: str, original: Exception | None = None, provider: str = ""):
        if reason not in ALL_REASONS:
            raise ValueError(f"unknown LLM error reason: {reason!r}")
        self.reason = reason
        self.user_message = user_message
        self.original = original
        self.provider = provider
        super().__init__(f"[{provider or 'llm'}] {reason}: {original}")


# ---- canonical request/response shapes -------------------------------------
# Deliberately duck-type compatible with the subset of the OpenAI SDK's
# ChatCompletionMessage that the rest of the app already reads
# (`.content`, `.tool_calls`, each tool_call's `.id`/`.function.name`/
# `.function.arguments`) - existing callers (llm_reply.py,
# conversation_service.py, the tools) need no changes at all.

@dataclass
class ToolCallFunction:
    name: str
    arguments: str  # JSON-encoded string - the wire format every caller already expects


@dataclass
class ToolCall:
    id: str
    function: ToolCallFunction
    type: str = "function"


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[ToolCall] | None = None


class LLMProvider(abc.ABC):
    """One provider adapter. `name` identifies it in logs/status output
    (never a secret). Implementations: openai_compatible.py (shared by
    Groq/OpenRouter/Ollama - all three speak the same OpenAI chat/
    completions schema) and gemini_provider.py (a genuinely different
    API, given its own real adapter rather than forced through the
    OpenAI shape)."""

    name: str = "unknown"

    @abc.abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.4,
    ) -> ChatResult:
        """messages: OpenAI-shaped [{"role": "system"|"user"|"assistant"|"tool",
        "content": ...}] (+ "tool_call_id" on tool-role messages,
        "tool_calls" on assistant-role messages that made one) - this is
        the one wire format every caller in the app already builds;
        adapters translate it to/from their own provider's native shape
        internally, never the other way around.
        tools: OpenAI-style tool/function definitions, or None.
        Must raise LLMProviderError (never the provider's own exception
        type) on any failure - never let a raw provider exception escape
        the adapter."""
        raise NotImplementedError

    @abc.abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError
