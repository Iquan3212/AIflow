"""
Gemini adapter via Google's current `google-genai` SDK (the supported
client library - not the older, deprecated `google-generativeai` package).

Gemini's API shape differs from OpenAI's in ways this adapter bridges, so
every other module can keep building the one OpenAI-shaped message list it
already builds today:

- No "system" role inside the message array - system instructions are a
  separate `system_instruction` config field. Every system-role message in
  the input (there can be several: the hardened system prompt, known
  facts, tool-result grounding, the injection-reinforcement reminder) is
  concatenated, in order, into one system_instruction string.
- Roles are "user"/"model", not "user"/"assistant".
- Function/tool calling uses a different schema (FunctionDeclaration/Tool)
  and a different round-trip shape: a function call/result is a `Part`
  inside a `Content`, not a flat "tool"-role message keyed by
  tool_call_id. `_to_gemini_contents` tracks which function NAME each
  tool_call_id belongs to (from the preceding assistant-role message) so a
  later "tool" role message - which, in the OpenAI shape every caller
  already uses, only carries the id - can still be turned into a
  correctly-named Gemini functionResponse part.
"""

from __future__ import annotations

import json

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

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


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self._model = model
        self._client = genai.Client(api_key=api_key)

    def model_name(self) -> str:
        return self._model

    def chat(self, messages, tools=None, tool_choice="auto", temperature: float = 0.4) -> ChatResult:
        system_instruction, contents = _to_gemini_contents(messages)

        config_kwargs: dict = {"temperature": temperature}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if tools:
            config_kwargs["tools"] = [_to_gemini_tool(tools)]
            config_kwargs["tool_config"] = genai_types.ToolConfig(
                function_calling_config=genai_types.FunctionCallingConfig(
                    mode="AUTO" if tool_choice == "auto" else "ANY",
                )
            )
        config = genai_types.GenerateContentConfig(**config_kwargs)

        try:
            response = self._client.models.generate_content(model=self._model, contents=contents, config=config)
        except genai_errors.APIError as exc:
            reason, user_message = _classify_api_error(exc)
            raise LLMProviderError(reason, user_message, original=exc, provider=self.name) from exc
        except Exception as exc:
            # Connection-level failures (DNS, TLS, refused connection) from
            # the underlying httpx/requests transport don't subclass
            # genai_errors.APIError - there's no HTTP status code to read
            # a category from, so they're all "unavailable", matching the
            # OpenAI-compatible adapter's handling of the same situation.
            raise LLMProviderError(UNAVAILABLE, _UNAVAILABLE_MSG, original=exc, provider=self.name) from exc

        return _from_gemini_response(response)


def _to_gemini_contents(messages: list[dict]) -> tuple[str, list]:
    system_parts: list[str] = []
    contents: list = []
    tool_call_id_to_name: dict[str, str] = {}

    for msg in messages:
        role = msg.get("role")

        if role == "system":
            if msg.get("content"):
                system_parts.append(msg["content"])
            continue

        if role == "tool":
            name = tool_call_id_to_name.get(msg.get("tool_call_id"), "unknown_function")
            raw = msg.get("content")
            try:
                response_payload = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                response_payload = {"result": raw}
            if not isinstance(response_payload, dict):
                response_payload = {"result": response_payload}
            contents.append(genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_function_response(name=name, response=response_payload)],
            ))
            continue

        gemini_role = "model" if role == "assistant" else "user"
        parts = []
        for tc in msg.get("tool_calls") or []:
            tool_call_id_to_name[tc["id"]] = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            parts.append(genai_types.Part.from_function_call(name=tc["function"]["name"], args=args))
        if msg.get("content"):
            parts.append(genai_types.Part.from_text(text=msg["content"]))
        if not parts:
            continue
        contents.append(genai_types.Content(role=gemini_role, parts=parts))

    return "\n\n".join(system_parts), contents


def _to_gemini_tool(openai_tools: list[dict]) -> "genai_types.Tool":
    declarations = []
    for t in openai_tools:
        fn = t.get("function", t)
        declarations.append(genai_types.FunctionDeclaration(
            name=fn["name"],
            description=fn.get("description", ""),
            parameters_json_schema=fn.get("parameters") or {"type": "object", "properties": {}},
        ))
    return genai_types.Tool(function_declarations=declarations)


def _from_gemini_response(response) -> ChatResult:
    if not response.candidates:
        return ChatResult(content=None, tool_calls=None)

    content_obj = response.candidates[0].content
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for i, part in enumerate((content_obj.parts if content_obj else None) or []):
        if getattr(part, "text", None):
            text_parts.append(part.text)
        fc = getattr(part, "function_call", None)
        if fc:
            tool_calls.append(ToolCall(
                id=fc.id or f"call_{i}",
                function=ToolCallFunction(name=fc.name, arguments=json.dumps(fc.args or {})),
            ))
    return ChatResult(content="\n".join(text_parts) or None, tool_calls=tool_calls or None)


def _classify_api_error(exc: "genai_errors.APIError") -> tuple[str, str]:
    """genai_errors.APIError.code is the real HTTP status code Gemini
    returned - a direct, documented attribute, not something inferred."""
    code = getattr(exc, "code", None)
    if code == 429:
        return RATE_LIMITED, _RATE_LIMIT_MSG
    if code in (401, 403):
        return AUTHENTICATION_ERROR, _UNAVAILABLE_MSG
    if code == 400:
        return INVALID_REQUEST, _INVALID_MSG
    if code in (408, 504):
        return TIMEOUT, _UNAVAILABLE_MSG
    if code is not None and code >= 500:
        return UNAVAILABLE, _UNAVAILABLE_MSG
    return PROVIDER_ERROR, _UNKNOWN_MSG
