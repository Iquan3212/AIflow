"""
create_llm_provider(settings, provider_name=None) -> LLMProvider

The one place in the app that turns LLM_PROVIDER (or an explicit override,
used to construct the fallback provider) into a concrete adapter instance.
No provider-specific branching exists anywhere else - llm_client.py calls
this once at import time for the primary provider and, if
LLM_FALLBACK_PROVIDER is set, once more for the fallback.
"""

from __future__ import annotations

from app.services.llm.base import LLMProvider
from app.services.llm.openai_compatible import OpenAICompatibleProvider

# Phase 11: Gemini was removed as a supported LLM_PROVIDER (see
# app/services/knowledge/embeddings.py's docstring for the full removal
# rationale - the same decision applies here for consistency, even though
# LLM_PROVIDER=gemini was never the active chat provider). If Gemini (or
# another provider) is ever reintroduced, add it back here explicitly -
# never resurrect the deleted app/services/llm/gemini_provider.py from
# history without re-auditing it first.
SUPPORTED_PROVIDERS = ("groq", "openrouter", "ollama")

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class UnsupportedProviderError(ValueError):
    """LLM_PROVIDER (or LLM_FALLBACK_PROVIDER) is set to something not in
    SUPPORTED_PROVIDERS."""


class ProviderNotConfiguredError(ValueError):
    """The *selected* provider is missing a setting it actually needs.
    Never raised for a provider that isn't selected - those providers'
    settings are allowed to stay blank; see config.py."""


def create_llm_provider(settings, provider_name: str | None = None) -> LLMProvider:
    name = (provider_name or settings.llm_provider or "groq").strip().lower()

    if name == "groq":
        # Falls back to the pre-refactor generic LLM_API_KEY/LLM_BASE_URL
        # fields when the new GROQ_API_KEY/GROQ_BASE_URL aren't set, so an
        # existing .env from before this refactor keeps working unchanged -
        # this is exactly how Groq was already configured.
        api_key = settings.groq_api_key or settings.llm_api_key
        if not api_key:
            raise ProviderNotConfiguredError("LLM_PROVIDER=groq requires GROQ_API_KEY (or the legacy LLM_API_KEY)")
        base_url = settings.groq_base_url or settings.llm_base_url or _GROQ_BASE_URL
        return OpenAICompatibleProvider(name="groq", api_key=api_key, base_url=base_url, model=settings.llm_model)

    if name == "openrouter":
        if not settings.openrouter_api_key:
            raise ProviderNotConfiguredError("LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY")
        return OpenAICompatibleProvider(
            name="openrouter",
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url or _OPENROUTER_BASE_URL,
            model=settings.llm_model,
            # Recommended (not required) by OpenRouter to identify traffic
            # in their dashboard - harmless if OpenRouter ignores them.
            extra_headers={"HTTP-Referer": settings.app_url, "X-Title": settings.app_name},
        )

    if name == "ollama":
        # No API key required for a local server - the OpenAI SDK just
        # needs a non-empty string, which OpenAICompatibleProvider supplies
        # on its own when none is given.
        base_url = (settings.ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
        return OpenAICompatibleProvider(name="ollama", api_key="", base_url=f"{base_url}/v1", model=settings.llm_model)

    raise UnsupportedProviderError(f"Unknown LLM provider {name!r} (supported: {', '.join(SUPPORTED_PROVIDERS)})")
