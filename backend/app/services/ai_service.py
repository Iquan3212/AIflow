from openai import OpenAI

from app.config import get_settings

settings = get_settings()

client = OpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
)


def ask_ai(history: list):
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=history,
        temperature=0.7,
    )

    return response.choices[0].message.content