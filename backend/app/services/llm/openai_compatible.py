"""
Shared adapter for every provider that speaks the OpenAI chat/completions
schema: Groq, OpenRouter, and a locally running Ollama server (via its own
OpenAI-compatible endpoint, `{OLLAMA_BASE_URL}/v1`). All three differ only
in base_url/api_key/model - there's no protocol difference significant
enough to warrant three separate adapters, and this is exactly how the
codebase already treated Groq before this refactor (its original docstring:
"works unmodified with OpenAI, Groq, Together, Fireworks, a self-hosted
vLLM/Ollama OpenAI-shim... swap providers by changing LLM_BASE_URL").
"""

from __future__ import annotations

import openai
from openai import OpenAI

from app.services.llm.base import (
    LLMProvider,
    ChatResult,
    ToolCall,
    ToolCallFunction,
    LLMProviderError,
    RATE_LIMITED,
    AUTHENTICATION_ERROR,
    TIMEOUT,
    UNAVAILABLE,
    INVALID_REQUEST,
    PROVIDER_ERROR,
)

_RATE_LIMIT_MSG = "Our AI assistant is getting a lot of requests right now. Please try again in a few minutes."
_UNAVAILABLE_MSG = "Our AI assistant is temporarily unavailable. Please try again shortly."
_INVALID_MSG = "Sorry, I couldn't process that request. Could you rephrase it?"
_UNKNOWN_MSG = "Sorry, I couldn't process that just now. Could you try again?"


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        extra_headers: dict | None = None,
    ):
        self.name = name
        self._model = model
        # Ollama doesn't check the key at all locally, but the SDK requires
        # a non-empty string to construct the client.
        self._client = OpenAI(api_key=api_key or "not-required", base_url=base_url)
        self._extra_headers = extra_headers or None

    def model_name(self) -> str:
        return self._model

    def chat(self, messages, tools=None, tool_choice="auto", temperature: float = 0.4) -> ChatResult:
        kwargs = {"model": self._model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        if self._extra_headers:
            kwargs["extra_headers"] = self._extra_headers

        try:
            response = self._client.chat.completions.create(**kwargs)
        except openai.APIError as exc:
            reason, user_message = _classify(exc)
            raise LLMProviderError(reason, user_message, original=exc, provider=self.name) from exc

        message = response.choices[0].message
        tool_calls = None
        if getattr(message, "tool_calls", None):
            tool_calls = [
                ToolCall(id=tc.id, function=ToolCallFunction(name=tc.function.name, arguments=tc.function.arguments))
                for tc in message.tool_calls
            ]
        return ChatResult(content=message.content, tool_calls=tool_calls)


def _classify(exc: "openai.APIError") -> tuple[str, str]:
    """openai.RateLimitError/AuthenticationError/APIConnectionError/etc.
    all inherit from openai.APIError - this only ever sees genuine
    provider-side failures. A bug in this app's own request construction
    (a TypeError from bad kwargs, say) is a different exception type
    entirely and is not caught by the narrower `except openai.APIError`
    above, so it still surfaces as itself rather than being misreported
    as a provider failure.

    APITimeoutError is checked before APIConnectionError because it is a
    *subclass* of it (both inherit the connection-level base) - isinstance
    order matters here."""
    if isinstance(exc, openai.RateLimitError):
        return RATE_LIMITED, _RATE_LIMIT_MSG
    if isinstance(exc, openai.APITimeoutError):
        return TIMEOUT, _UNAVAILABLE_MSG
    if isinstance(exc, (openai.APIConnectionError, openai.InternalServerError)):
        # Covers Ollama being unreachable (connection refused) as well as
        # a genuine provider-side 5xx - both are "try again shortly", not
        # a bug in this app.
        return UNAVAILABLE, _UNAVAILABLE_MSG
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        # A customer/owner never needs to know this is a config problem on
        # our end - same safe message as "unavailable", but logged under
        # its own reason so an operator can tell the difference (this
        # needs a human to fix credentials; "unavailable" usually
        # resolves on its own).
        return AUTHENTICATION_ERROR, _UNAVAILABLE_MSG
    if isinstance(exc, openai.BadRequestError):
        return INVALID_REQUEST, _INVALID_MSG
    return PROVIDER_ERROR, _UNKNOWN_MSG
