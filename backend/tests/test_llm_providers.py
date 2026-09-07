"""
Unit tests for the provider-agnostic LLM layer (app/services/llm/). All
network-touching pieces are mocked - these verify request/response/error
*mapping* deterministically, without needing real credentials for every
provider. Real, live verification (where credentials/a running server
were available) was performed separately - see ARCHITECTURE.md.

Run: python3 -m pytest tests/test_llm_providers.py -q   (from backend/)
"""

import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest
from google.genai import errors as genai_errors

from app.services.llm.base import (
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
    FALLBACK_ELIGIBLE_REASONS,
)
from app.services.llm.openai_compatible import OpenAICompatibleProvider
from app.services.llm import gemini_provider as gp
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.factory import (
    create_llm_provider,
    UnsupportedProviderError,
    ProviderNotConfiguredError,
)


def _settings(**overrides) -> SimpleNamespace:
    """Minimal stand-in for app.config.Settings, carrying only the fields
    create_llm_provider() actually reads. Using the real Settings class
    would require a full .env (database_url, jwt_secret, ...) unrelated to
    what's under test here."""
    base = dict(
        llm_provider="groq",
        llm_fallback_provider="",
        llm_model="test-model",
        llm_api_key="",
        llm_base_url="https://api.openai.com/v1",
        groq_api_key="",
        groq_base_url="",
        gemini_api_key="",
        openrouter_api_key="",
        openrouter_base_url="",
        ollama_base_url="http://127.0.0.1:11434",
        app_url="http://localhost:8000",
        app_name="AIFlow",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_openai_request():
    return httpx.Request("POST", "https://api.example.com/v1/chat/completions")


def _fake_message(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _fake_openai_tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def _fake_completion(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# =====================================================================
# GROQ / OPENROUTER / OLLAMA - shared OpenAICompatibleProvider
# =====================================================================

class TestOpenAICompatibleProvider:
    def _provider(self, name="groq"):
        with patch("app.services.llm.openai_compatible.OpenAI") as MockOpenAI:
            provider = OpenAICompatibleProvider(name=name, api_key="test-key", base_url="https://example.com/v1", model="test-model")
            return provider, MockOpenAI.return_value

    def test_configuration_uses_given_base_url_and_key(self):
        with patch("app.services.llm.openai_compatible.OpenAI") as MockOpenAI:
            OpenAICompatibleProvider(name="groq", api_key="sk-real", base_url="https://api.groq.com/openai/v1", model="m")
            MockOpenAI.assert_called_once_with(api_key="sk-real", base_url="https://api.groq.com/openai/v1")

    def test_configuration_ollama_accepts_blank_key(self):
        """Ollama needs no API key locally - the adapter must not choke on
        an empty string, and must still hand the SDK a non-empty
        placeholder (the SDK itself requires a truthy string)."""
        with patch("app.services.llm.openai_compatible.OpenAI") as MockOpenAI:
            OpenAICompatibleProvider(name="ollama", api_key="", base_url="http://127.0.0.1:11434/v1", model="llama3")
            _, kwargs = MockOpenAI.call_args
            assert kwargs["api_key"]  # non-empty placeholder, not ""

    def test_request_mapping_plain_chat(self):
        provider, mock_client = self._provider()
        mock_client.chat.completions.create.return_value = _fake_completion(_fake_message(content="hello"))

        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
        result = provider.chat(messages, temperature=0.7)

        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["model"] == "test-model"
        assert kwargs["messages"] == messages
        assert kwargs["temperature"] == 0.7
        assert "tools" not in kwargs  # no tools passed in -> not forwarded at all
        assert isinstance(result, ChatResult)
        assert result.content == "hello"
        assert result.tool_calls is None

    def test_request_mapping_with_tools(self):
        provider, mock_client = self._provider()
        mock_client.chat.completions.create.return_value = _fake_completion(_fake_message(content=None))
        tools = [{"type": "function", "function": {"name": "book", "parameters": {}}}]

        provider.chat([{"role": "user", "content": "book me"}], tools=tools, tool_choice="auto")

        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["tools"] == tools
        assert kwargs["tool_choice"] == "auto"

    def test_response_mapping_with_tool_calls(self):
        provider, mock_client = self._provider()
        mock_client.chat.completions.create.return_value = _fake_completion(
            _fake_message(content=None, tool_calls=[_fake_openai_tool_call("call_1", "book_appointment", '{"time":"3pm"}')])
        )

        result = provider.chat([{"role": "user", "content": "book"}], tools=[{"type": "function", "function": {"name": "book_appointment"}}])

        assert result.content is None
        assert result.tool_calls == [ToolCall(id="call_1", function=ToolCallFunction(name="book_appointment", arguments='{"time":"3pm"}'))]

    def test_extra_headers_forwarded_when_configured(self):
        with patch("app.services.llm.openai_compatible.OpenAI") as MockOpenAI:
            provider = OpenAICompatibleProvider(
                name="openrouter", api_key="k", base_url="https://openrouter.ai/api/v1", model="m",
                extra_headers={"HTTP-Referer": "https://aiflow.example", "X-Title": "AIFlow"},
            )
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.return_value = _fake_completion(_fake_message(content="ok"))
            provider.chat([{"role": "user", "content": "hi"}])
            _, kwargs = mock_client.chat.completions.create.call_args
            assert kwargs["extra_headers"] == {"HTTP-Referer": "https://aiflow.example", "X-Title": "AIFlow"}

    @pytest.mark.parametrize("build_exc,expected_reason", [
        (lambda: openai.RateLimitError("rate limited", response=httpx.Response(429, request=_fake_openai_request(), json={}), body={}), RATE_LIMITED),
        (lambda: openai.AuthenticationError("bad key", response=httpx.Response(401, request=_fake_openai_request(), json={}), body={}), AUTHENTICATION_ERROR),
        (lambda: openai.PermissionDeniedError("forbidden", response=httpx.Response(403, request=_fake_openai_request(), json={}), body={}), AUTHENTICATION_ERROR),
        (lambda: openai.BadRequestError("bad request", response=httpx.Response(400, request=_fake_openai_request(), json={}), body={}), INVALID_REQUEST),
        (lambda: openai.InternalServerError("boom", response=httpx.Response(500, request=_fake_openai_request(), json={}), body={}), UNAVAILABLE),
        (lambda: openai.APIConnectionError(request=_fake_openai_request()), UNAVAILABLE),
        (lambda: openai.APITimeoutError(request=_fake_openai_request()), TIMEOUT),
        (lambda: openai.ConflictError("conflict", response=httpx.Response(409, request=_fake_openai_request(), json={}), body={}), PROVIDER_ERROR),
    ])
    def test_error_classification(self, build_exc, expected_reason):
        provider, mock_client = self._provider()
        mock_client.chat.completions.create.side_effect = build_exc()

        with pytest.raises(LLMProviderError) as excinfo:
            provider.chat([{"role": "user", "content": "hi"}])

        assert excinfo.value.reason == expected_reason
        assert excinfo.value.provider == "groq"
        # The user-facing message must never leak provider-specific detail.
        assert "org_" not in excinfo.value.user_message
        assert "billing" not in excinfo.value.user_message.lower()

    def test_non_provider_exception_is_not_reclassified(self):
        """A bug in this app's own code (e.g. a TypeError from malformed
        kwargs) must surface as itself, never be mislabeled as a provider
        failure - only openai.APIError subclasses are caught."""
        provider, mock_client = self._provider()
        mock_client.chat.completions.create.side_effect = TypeError("boom")

        with pytest.raises(TypeError):
            provider.chat([{"role": "user", "content": "hi"}])


# =====================================================================
# GEMINI
# =====================================================================

class TestGeminiProvider:
    def test_configuration(self):
        with patch("app.services.llm.gemini_provider.genai") as mock_genai:
            GeminiProvider(api_key="test-gemini-key", model="gemini-2.0-flash")
            mock_genai.Client.assert_called_once_with(api_key="test-gemini-key")

    def test_request_mapping_system_messages_concatenated(self):
        """Multiple system-role messages (hardened prompt, known facts,
        tool-result grounding, injection reminder) must all end up in one
        system_instruction string, in order - Gemini has no per-message
        system role to put them in individually."""
        messages = [
            {"role": "system", "content": "You are the assistant."},
            {"role": "system", "content": "Known facts: name=Sam"},
            {"role": "user", "content": "hi"},
        ]
        system_instruction, contents = gp._to_gemini_contents(messages)
        assert system_instruction == "You are the assistant.\n\nKnown facts: name=Sam"
        assert len(contents) == 1
        assert contents[0].role == "user"

    def test_request_mapping_role_translation(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        _, contents = gp._to_gemini_contents(messages)
        assert [c.role for c in contents] == ["user", "model"]

    def test_request_mapping_tool_round_trip(self):
        """assistant message with a tool_call, followed by a tool-role
        result (the OpenAI shape every caller already builds) must become
        a function_call Content followed by a function_response Content
        carrying the CORRECT function name - which the tool-role message
        alone doesn't have, only the tool_call_id."""
        messages = [
            {"role": "user", "content": "book a haircut"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call_1", "function": {"name": "check_availability", "arguments": '{"date": "2026-08-04"}'}}
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": '{"ok": true, "available": true}'},
        ]
        _, contents = gp._to_gemini_contents(messages)

        assert len(contents) == 3
        call_part = contents[1].parts[0]
        assert call_part.function_call.name == "check_availability"
        assert call_part.function_call.args == {"date": "2026-08-04"}

        response_part = contents[2].parts[0]
        assert response_part.function_response.name == "check_availability"
        assert response_part.function_response.response == {"ok": True, "available": True}

    def test_tool_definition_mapping(self):
        openai_tools = [{
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": "Books a slot",
                "parameters": {"type": "object", "properties": {"time": {"type": "string"}}},
            },
        }]
        tool = gp._to_gemini_tool(openai_tools)
        assert len(tool.function_declarations) == 1
        decl = tool.function_declarations[0]
        assert decl.name == "book_appointment"
        assert decl.description == "Books a slot"

    def test_response_mapping_text_only(self):
        response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(
            parts=[SimpleNamespace(text="Hi there!", function_call=None)]
        ))])
        result = gp._from_gemini_response(response)
        assert result.content == "Hi there!"
        assert result.tool_calls is None

    def test_response_mapping_function_call(self):
        fc = SimpleNamespace(id="fc1", name="check_availability", args={"date": "2026-08-04"})
        response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(
            parts=[SimpleNamespace(text=None, function_call=fc)]
        ))])
        result = gp._from_gemini_response(response)
        assert result.content is None
        assert result.tool_calls == [ToolCall(id="fc1", function=ToolCallFunction(name="check_availability", arguments='{"date": "2026-08-04"}'))]

    def test_response_mapping_no_candidates(self):
        response = SimpleNamespace(candidates=[])
        result = gp._from_gemini_response(response)
        assert result == ChatResult(content=None, tool_calls=None)

    @pytest.mark.parametrize("code,expected_reason", [
        (429, RATE_LIMITED),
        (401, AUTHENTICATION_ERROR),
        (403, AUTHENTICATION_ERROR),
        (400, INVALID_REQUEST),
        (408, TIMEOUT),
        (504, TIMEOUT),
        (500, UNAVAILABLE),
        (503, UNAVAILABLE),
        (418, PROVIDER_ERROR),
    ])
    def test_error_classification(self, code, expected_reason):
        exc = genai_errors.APIError(code, {"error": {"message": "boom"}})
        reason, _ = gp._classify_api_error(exc)
        assert reason == expected_reason

    def test_chat_wraps_api_error(self):
        with patch("app.services.llm.gemini_provider.genai") as mock_genai:
            provider = GeminiProvider(api_key="k", model="m")
            mock_genai.Client.return_value.models.generate_content.side_effect = genai_errors.APIError(429, {"error": {}})
            with pytest.raises(LLMProviderError) as excinfo:
                provider.chat([{"role": "user", "content": "hi"}])
            assert excinfo.value.reason == RATE_LIMITED
            assert excinfo.value.provider == "gemini"

    def test_chat_wraps_connection_failure_as_unavailable(self):
        """A network-level failure (DNS, refused connection, TLS) doesn't
        subclass genai_errors.APIError - there's no status code to read a
        category from, so it must still become a clean, classified
        LLMProviderError, never a raw exception escaping the adapter."""
        with patch("app.services.llm.gemini_provider.genai") as mock_genai:
            provider = GeminiProvider(api_key="k", model="m")
            mock_genai.Client.return_value.models.generate_content.side_effect = ConnectionError("refused")
            with pytest.raises(LLMProviderError) as excinfo:
                provider.chat([{"role": "user", "content": "hi"}])
            assert excinfo.value.reason == UNAVAILABLE


# =====================================================================
# FACTORY
# =====================================================================

class TestFactory:
    def test_groq_selected_with_new_key(self):
        settings = _settings(llm_provider="groq", groq_api_key="gk")
        provider = create_llm_provider(settings)
        assert provider.name == "groq"
        assert provider.model_name() == "test-model"

    def test_groq_falls_back_to_legacy_llm_api_key(self):
        """Preserves pre-refactor .env files that only set LLM_API_KEY."""
        settings = _settings(llm_provider="groq", groq_api_key="", llm_api_key="legacy-key")
        provider = create_llm_provider(settings)
        assert provider.name == "groq"

    def test_groq_missing_key_raises(self):
        settings = _settings(llm_provider="groq", groq_api_key="", llm_api_key="")
        with pytest.raises(ProviderNotConfiguredError):
            create_llm_provider(settings)

    def test_gemini_selected_correctly(self):
        settings = _settings(llm_provider="gemini", gemini_api_key="gem-key")
        with patch("app.services.llm.gemini_provider.genai"):
            provider = create_llm_provider(settings)
        assert provider.name == "gemini"

    def test_gemini_missing_key_raises(self):
        settings = _settings(llm_provider="gemini", gemini_api_key="")
        with pytest.raises(ProviderNotConfiguredError):
            create_llm_provider(settings)

    def test_openrouter_selected_correctly(self):
        settings = _settings(llm_provider="openrouter", openrouter_api_key="or-key")
        with patch("app.services.llm.openai_compatible.OpenAI"):
            provider = create_llm_provider(settings)
        assert provider.name == "openrouter"

    def test_openrouter_missing_key_raises(self):
        settings = _settings(llm_provider="openrouter", openrouter_api_key="")
        with pytest.raises(ProviderNotConfiguredError):
            create_llm_provider(settings)

    def test_ollama_selected_correctly_without_any_key(self):
        settings = _settings(llm_provider="ollama")
        with patch("app.services.llm.openai_compatible.OpenAI"):
            provider = create_llm_provider(settings)
        assert provider.name == "ollama"

    def test_ollama_uses_configured_base_url(self):
        settings = _settings(llm_provider="ollama", ollama_base_url="http://192.168.1.50:11434")
        with patch("app.services.llm.openai_compatible.OpenAI") as MockOpenAI:
            create_llm_provider(settings)
            _, kwargs = MockOpenAI.call_args
            assert kwargs["base_url"] == "http://192.168.1.50:11434/v1"

    def test_invalid_provider_rejected(self):
        settings = _settings(llm_provider="not-a-real-provider")
        with pytest.raises(UnsupportedProviderError):
            create_llm_provider(settings)

    def test_only_selected_providers_credentials_required(self):
        """Selecting groq must never require GEMINI_API_KEY/
        OPENROUTER_API_KEY to be set - unused providers' settings are
        allowed to stay blank."""
        settings = _settings(llm_provider="groq", groq_api_key="gk", gemini_api_key="", openrouter_api_key="")
        provider = create_llm_provider(settings)  # must not raise
        assert provider.name == "groq"


# =====================================================================
# FALLBACK (exercised through llm_client.chat_completion, monkeypatching
# its module-level provider instances - the same objects a real request
# calls through, without needing real credentials for either provider)
# =====================================================================

class TestFallback:
    def _run_with_providers(self, primary, fallback, messages=None):
        import app.services.llm_client as llm_client_module
        with patch.object(llm_client_module, "_provider", primary), \
             patch.object(llm_client_module, "_fallback_provider", fallback):
            return llm_client_module.chat_completion(messages or [{"role": "user", "content": "hi"}])

    def test_fallback_used_for_eligible_reason(self):
        primary = MagicMock(name="primary")
        primary.name = "gemini"
        primary.model_name.return_value = "gemini-model"
        primary.chat.side_effect = LLMProviderError(RATE_LIMITED, "busy", provider="gemini")

        fallback = MagicMock(name="fallback")
        fallback.name = "groq"
        fallback.model_name.return_value = "groq-model"
        fallback.chat.return_value = ChatResult(content="fallback reply")

        result = self._run_with_providers(primary, fallback)

        assert result.content == "fallback reply"
        fallback.chat.assert_called_once()

    def test_no_fallback_configured_reraises(self):
        primary = MagicMock(name="primary")
        primary.name = "gemini"
        primary.model_name.return_value = "gemini-model"
        primary.chat.side_effect = LLMProviderError(UNAVAILABLE, "down", provider="gemini")

        with pytest.raises(LLMProviderError):
            self._run_with_providers(primary, None)

    @pytest.mark.parametrize("reason", [INVALID_REQUEST, AUTHENTICATION_ERROR])
    def test_no_fallback_for_ineligible_reasons(self, reason):
        """A malformed request or an auth problem in OUR app fails
        identically on any other provider - falling back would just waste
        a second call, so these must always re-raise instead."""
        assert reason not in FALLBACK_ELIGIBLE_REASONS

        primary = MagicMock(name="primary")
        primary.name = "gemini"
        primary.model_name.return_value = "gemini-model"
        primary.chat.side_effect = LLMProviderError(reason, "nope", provider="gemini")

        fallback = MagicMock(name="fallback")
        fallback.name = "groq"

        with pytest.raises(LLMProviderError):
            self._run_with_providers(primary, fallback)
        fallback.chat.assert_not_called()

    def test_fallback_failure_propagates_without_recursion(self):
        """Exactly one fallback attempt - if IT also fails, that failure
        propagates; there is no third provider, no retry loop."""
        primary = MagicMock(name="primary")
        primary.name = "gemini"
        primary.model_name.return_value = "gemini-model"
        primary.chat.side_effect = LLMProviderError(TIMEOUT, "slow", provider="gemini")

        fallback = MagicMock(name="fallback")
        fallback.name = "groq"
        fallback.model_name.return_value = "groq-model"
        fallback.chat.side_effect = LLMProviderError(UNAVAILABLE, "also down", provider="groq")

        with pytest.raises(LLMProviderError) as excinfo:
            self._run_with_providers(primary, fallback)
        assert excinfo.value.provider == "groq"  # the fallback's own failure, not a retried primary
        assert fallback.chat.call_count == 1


# =====================================================================
# ERROR MODEL SANITY
# =====================================================================

def test_invalid_reason_rejected():
    with pytest.raises(ValueError):
        LLMProviderError("not_a_real_reason", "message")


def test_all_canonical_reasons_are_distinct():
    assert len({RATE_LIMITED, AUTHENTICATION_ERROR, TIMEOUT, UNAVAILABLE, INVALID_REQUEST, PROVIDER_ERROR}) == 6
