"""
Thin wrapper around any OpenAI-compatible chat completions API.

Works unmodified with OpenAI, Groq, Together, Fireworks, a self-hosted
vLLM/Ollama OpenAI-shim, or any other provider that speaks the same
/chat/completions schema. Swap providers by changing LLM_BASE_URL and
LLM_API_KEY in .env — nothing in this file or the rest of the app changes.
"""

from openai import OpenAI

from app.config import get_settings

settings = get_settings()

_client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto"):
    """
    messages: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
    tools: OpenAI-style tool/function definitions (optional)
    Returns the raw completion message object (choices[0].message).
    """
    kwargs = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.4,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    response = _client.chat.completions.create(**kwargs)
    return response.choices[0].message
