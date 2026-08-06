from app.agents.memory import ConversationMemory


class SalesAgent:
    """
    AI Workforce - Sales Employee

    Responsibilities:
    - Handle pricing questions
    - Generate quotations
    - Recommend services
    - Upsell
    - Capture buying intent
    """

    def __init__(self, business, lead=None):

        self.business = business
        self.lead = lead
        self.memory = ConversationMemory()

    @property
    def system_prompt(self) -> str:

        services = []

        if (
            hasattr(self.business, "chatbot_config")
            and self.business.chatbot_config
            and self.business.chatbot_config.services
        ):
            services = self.business.chatbot_config.services

        services_text = "\n".join(
            f"- {service}"
            for service in services
        )

        return f"""
You are the Sales AI for {self.business.name}.

ROLE

You are responsible for helping customers
purchase products and services.

YOUR RESPONSIBILITIES

- Recommend services

- Explain pricing

- Generate quotations

- Upsell naturally

- Capture buying intent

RULES

Never invent prices.

Never invent discounts.

Never invent products.

Only recommend services listed below.

SERVICES

{services_text if services_text else "No services configured."}

Always remain friendly and professional.
"""

    def analyze(
        self,
        message: str,
        history,
    ) -> dict:

        context = self.memory.shared_context(history)

        buying_keywords = [

            "price",

            "cost",

            "quotation",

            "quote",

            "buy",

            "purchase",

            "discount",

            "finance",

            "emi",

        ]

        buying_intent = any(

            word in message.lower()

            for word in buying_keywords

        )

        return {

            "employee": "sales",

            "intent": "sales",

            "buying_intent": buying_intent,

            "memory": context,

            "system_prompt": self.system_prompt,

        }

    def handoff(self):

        """
        Employees that Sales AI may delegate to.
        """

        return [

            "receptionist",

            "finance",

            "support",

        ]