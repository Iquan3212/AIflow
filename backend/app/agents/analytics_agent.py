from app.agents.llm_reply import facts_context, generate_employee_reply
from app.agents.memory import ConversationMemory


class AnalyticsAgent:
    """
    AI Workforce - Analytics AI

    Responsibilities

    - Dashboard insights

    - Lead summaries

    - Appointment summaries

    - Business analytics

    - KPI explanations
    """

    def __init__(self, business, lead=None):

        self.business = business
        self.lead = lead

        self.memory = ConversationMemory()

    @property
    def system_prompt(self):

        return f"""
You are the Analytics AI for {self.business.name}.

ROLE

Help the business owner understand business performance.

RESPONSIBILITIES

- Explain dashboard statistics

- Summarize leads

- Explain appointments

- Explain trends

RULES

Never invent statistics.

Only explain available business data.

Always present insights clearly.
"""

    def analyze(
        self,
        message,
        history,
    ):

        context = self.memory.shared_context(history)

        analytics_keywords = [

            "dashboard",

            "analytics",

            "report",

            "summary",

            "performance",

            "statistics",

            "revenue",

            "growth",

            "lead",

        ]

        detected = any(

            word in message.lower()

            for word in analytics_keywords

        )

        return {

            "employee": "analytics",

            "intent": "analytics",

            "analytics_detected": detected,

            "memory": context,

            "system_prompt": self.system_prompt,

        }

    def respond(self, message: str, history, tool_router=None) -> dict:
        analysis = self.analyze(message, history)

        tool_result = None
        if tool_router is not None:
            res = tool_router.execute(employee="analytics", tool_name="dashboard", message=message)
            if res.get("success"):
                tool_result = res.get("result")

        reply = generate_employee_reply(
            "analytics", self.system_prompt, message, history,
            tool_result=tool_result, extra_context=facts_context(analysis),
        )
        analysis["reply"] = reply
        analysis["tool_result"] = tool_result
        return analysis

    def handoff(self):

        return [

            "manager",

        ]