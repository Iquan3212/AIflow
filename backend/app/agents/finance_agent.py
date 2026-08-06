from app.agents.memory import ConversationMemory


class FinanceAgent:
    """
    AI Workforce - Finance AI

    Responsibilities
    ----------------
    - Estimate budgets
    - Finance enquiries
    - EMI discussions
    - Invoice guidance
    - Quote preparation
    """

    def __init__(self, business, lead=None):

        self.business = business
        self.lead = lead
        self.memory = ConversationMemory()

    @property
    def system_prompt(self):

        return f"""
You are the Finance AI for {self.business.name}.

ROLE

You help customers with finance-related questions.

RESPONSIBILITIES

- Explain financing options

- Help estimate budgets

- Discuss quotations

- Explain invoices

RULES

Never invent prices.

Never invent financing offers.

Never promise approvals.

Always remain professional.
"""

    def analyze(
        self,
        message: str,
        history,
    ):

        context = self.memory.shared_context(history)

        keywords = [

            "finance",

            "emi",

            "loan",

            "budget",

            "quotation",

            "invoice",

            "payment",

            "price",

        ]

        detected = any(

            word in message.lower()

            for word in keywords

        )

        return {

            "employee": "finance",

            "intent": "finance",

            "finance_detected": detected,

            "memory": context,

            "system_prompt": self.system_prompt,

        }

    def handoff(self):

        return [

            "sales",

            "manager",

        ]