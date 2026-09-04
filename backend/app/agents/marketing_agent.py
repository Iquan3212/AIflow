from app.agents.llm_reply import facts_context, generate_employee_reply
from app.agents.memory import ConversationMemory


class MarketingAgent:
    """
    AI Workforce - Marketing AI

    Responsibilities

    - Social media

    - Campaign ideas

    - Captions

    - Promotions

    - Content writing
    """

    def __init__(self, business, lead=None):

        self.business = business
        self.lead = lead

        self.memory = ConversationMemory()

    @property
    def system_prompt(self):

        return f"""
You are the Marketing AI for {self.business.name}.

ROLE

Create marketing content.

RESPONSIBILITIES

- Instagram captions

- Facebook posts

- Promotional campaigns

- Marketing ideas

RULES

Never invent business facts.

Only use information supplied by the business.

Keep writing engaging and concise.
"""

    def analyze(
        self,
        message,
        history,
    ):

        context = self.memory.shared_context(history)

        marketing_keywords = [

            "instagram",

            "facebook",

            "campaign",

            "caption",

            "promotion",

            "marketing",

            "advertisement",

        ]

        detected = any(

            word in message.lower()

            for word in marketing_keywords

        )

        return {

            "employee": "marketing",

            "intent": "marketing",

            "marketing_detected": detected,

            "memory": context,

            "system_prompt": self.system_prompt,

        }

    def respond(self, message: str, history, tool_router=None) -> dict:
        analysis = self.analyze(message, history)

        tool_result = None
        if tool_router is not None and analysis.get("marketing_detected"):
            res = tool_router.execute(employee="marketing", tool_name="campaign", message=message)
            if res.get("success"):
                tool_result = res.get("result")

        reply = generate_employee_reply(
            "marketing", self.system_prompt, message, history,
            tool_result=tool_result, extra_context=facts_context(analysis),
        )
        analysis["reply"] = reply
        analysis["tool_result"] = tool_result
        return analysis

    def handoff(self):

        return [

            "sales",

            "manager",

        ]