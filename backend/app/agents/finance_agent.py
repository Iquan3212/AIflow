from app.agents.llm_reply import generate_employee_reply
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

    def respond(self, message: str, history, tool_router=None) -> dict:
        analysis = self.analyze(message, history)

        tool_result = None
        if tool_router is not None and analysis.get("finance_detected"):
            res = tool_router.execute(employee="finance", tool_name="quotation", message=message)
            if res.get("success"):
                tool_result = res.get("result")

        reply = generate_employee_reply("finance", self.system_prompt, message, history, tool_result=tool_result)
        analysis["reply"] = reply
        analysis["tool_result"] = tool_result
        return analysis

    def handoff(self):

        return [

            "sales",

            "manager",

        ]