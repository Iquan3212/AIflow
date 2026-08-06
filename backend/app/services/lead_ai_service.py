import json
import re

from openai import OpenAI

from app.config import get_settings

settings = get_settings()

client = OpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
)


def extract_lead_information(message: str):

    prompt = f"""
You are an information extraction system.

Extract customer information from the message.

Return ONLY valid JSON.

Do not explain anything.

Do not wrap the JSON in markdown.

Return exactly this format:

{{
  "buying_intent": true,
  "name": null,
  "phone": null,
  "email": null,
  "service_interested": null,
  "budget": null
}}

Customer message:

{message}
"""

    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    content = response.choices[0].message.content.strip()

    print("\n========== LLM RESPONSE ==========")
    print(content)
    print("==================================\n")

    # Remove markdown fences if present
    content = re.sub(r"^```json", "", content, flags=re.IGNORECASE).strip()
    content = re.sub(r"^```", "", content).strip()
    content = re.sub(r"```$", "", content).strip()

    try:
        return json.loads(content)

    except json.JSONDecodeError:

        print("Invalid JSON received:")
        print(content)

        return {
            "buying_intent": False,
            "name": None,
            "phone": None,
            "email": None,
            "service_interested": None,
            "budget": None,
        }