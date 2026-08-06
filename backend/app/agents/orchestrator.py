from app.agents.planner import Planner
from app.agents.memory import ConversationMemory
from app.agents.tool_router import ToolRouter

from app.agents.sales_agent import SalesAgent
from app.agents.support_agent import SupportAgent


class AIOrchestrator:
    """
    Phase 5 AI Workforce Orchestrator

    Responsibilities

    1. Understand user intent.
    2. Select the correct AI Employee.
    3. Build shared memory.
    4. Execute tools when appropriate.
    5. Pass context to the LLM.
    """

    def __init__(
        self,
        db,
        business,
        conversation,
        lead,
    ):

        self.db = db
        self.business = business
        self.conversation = conversation
        self.lead = lead

        self.planner = Planner()

        self.memory = ConversationMemory()

        self.router = ToolRouter(
            db=db,
            business=business,
            conversation=conversation,
            lead=lead,
        )

        self.sales_agent = SalesAgent(
            business,
            lead,
        )

        self.support_agent = SupportAgent(
            business,
            lead,
        )

    def before_llm(
        self,
        message: str,
        history=None,
    ):

        history = history or []

        plan = self.planner.plan(message)

        shared_memory = self.memory.shared_context(history)

        employee_context = self._dispatch_employee(
            plan.agent,
            message,
            history,
        )

        tool_result = None

        if plan.tool:

            tool_result = self.router.execute(
                employee=plan.agent,
                tool_name=plan.tool,
                message=message,
            )

        return {

            "plan": plan,

            "memory": shared_memory["summary"],

            "shared_memory": shared_memory,

            "employee": employee_context,

            "tool_result": tool_result,

        }

    def _dispatch_employee(
        self,
        employee: str,
        message: str,
        history,
    ):

        if employee == "sales":

            return self.sales_agent.analyze(
                message,
                history,
            )

        if employee == "support":

            return self.support_agent.analyze(
                message,
                history,
            )

        return {

            "employee": "manager",

            "intent": "general",

            "system_prompt": "",

            "memory": self.memory.shared_context(
                history,
            ),

        }

    def after_llm(
        self,
        reply: str,
    ):

        return reply