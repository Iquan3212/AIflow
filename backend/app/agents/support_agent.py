from app.agents.llm_reply import generate_employee_reply
from app.agents.memory import ConversationMemory


class SupportAgent:
    """
    AI Workforce - Customer Support Employee

    Responsibilities
    ----------------
    - Handle customer issues
    - Answer support questions
    - Explain business policies
    - Handle complaints
    - Escalate when necessary
    """

    def __init__(self, business, lead=None):

        self.business = business
        self.lead = lead
        self.memory = ConversationMemory()

    @property
    def system_prompt(self) -> str:

        return f"""
You are the Customer Support AI for {self.business.name}.

ROLE

You are responsible for helping existing and new customers
solve problems professionally.

YOUR RESPONSIBILITIES

- Answer customer questions

- Help resolve issues

- Explain company policies

- Help with refunds when information is available

- Help with appointments

RULES

Never invent policies.

Never invent refund rules.

Never invent business information.

If you do not know the answer,
say so politely.

Always remain calm,
professional,
friendly
and empathetic.

Never argue with customers.

Always try to solve the customer's issue.
"""

    def analyze(
        self,
        message: str,
        history,
    ) -> dict:

        context = self.memory.shared_context(history)

        issue_keywords = [

            "problem",

            "issue",

            "refund",

            "broken",

            "error",

            "help",

            "complaint",

            "cancel",

            "not working",

            "failed",

            "wrong",

        ]

        issue_detected = any(

            word in message.lower()

            for word in issue_keywords

        )

        priority = "normal"

        if any(

            word in message.lower()

            for word in [

                "angry",

                "urgent",

                "immediately",

                "complaint",

                "legal",

            ]

        ):

            priority = "high"

        return {

            "employee": "support",

            "intent": "support",

            "issue_detected": issue_detected,

            "priority": priority,

            "memory": context,

            "system_prompt": self.system_prompt,

        }

    def respond(self, message: str, history, tool_router=None) -> dict:
        analysis = self.analyze(message, history)
        reply = generate_employee_reply("support", self.system_prompt, message, history)
        analysis["reply"] = reply
        analysis["tool_result"] = None
        return analysis

    def handoff(self):

        """
        AI employees that Support AI may delegate work to.
        """

        return [

            "sales",

            "receptionist",

            "manager",

        ]