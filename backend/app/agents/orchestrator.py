from typing import Any

from app.agents.planner import Planner
from app.agents.memory import ConversationMemory
from app.agents.registry import Registry
from app.agents.tool_router import ToolRouter
from app.agents.manager_agent import ManagerAgent

from app.agents.sales_agent import SalesAgent
from app.agents.support_agent import SupportAgent
from app.agents.receptionist_agent import ReceptionistAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.marketing_agent import MarketingAgent
from app.agents.finance_agent import FinanceAgent

from app.tools.lead_tool import LeadTool
from app.tools.appointment_tool import AppointmentTool
from app.tools.quotation_tool import QuotationTool
from app.tools.campaign_tool import CampaignTool
from app.tools.analytics_tool import AnalyticsTool


class AIOrchestrator:
    """
    Phase 5 AI Workforce Orchestrator composing:
    Planner -> ManagerAgent -> Employees -> ToolRouter -> real services (LLM/DB)
    """

    def __init__(self, db: Any, business: Any, conversation: Any, lead: Any):
        self.db = db
        self.business = business
        self.conversation = conversation
        self.lead = lead

        # Core components
        self.planner = Planner()
        self.memory = ConversationMemory()
        self.registry = Registry(db=db)

        # Tools are real project modules; a failure here is a bug, not an
        # expected condition, so it is not swallowed.
        self.registry.register_tool("lead", LeadTool(db=self.db))
        self.registry.register_tool("appointment", AppointmentTool(db=self.db))
        self.registry.register_tool("quotation", QuotationTool(db=self.db))
        self.registry.register_tool("campaign", CampaignTool(db=self.db))
        self.registry.register_tool("dashboard", AnalyticsTool(db=self.db))

        # Employee agents
        self.registry.register_employee("sales", SalesAgent(self.business, self.lead), tools=["lead"])
        self.registry.register_employee("support", SupportAgent(self.business, self.lead), tools=[])
        self.registry.register_employee(
            "receptionist", ReceptionistAgent(self.business, self.lead), tools=["appointment"]
        )
        self.registry.register_employee("analytics", AnalyticsAgent(self.business, self.lead), tools=["dashboard"])
        self.registry.register_employee("marketing", MarketingAgent(self.business, self.lead), tools=["campaign"])
        self.registry.register_employee("finance", FinanceAgent(self.business, self.lead), tools=["quotation"])

        # Manager gets access to all registered tools and orchestrates employees
        self.router = ToolRouter(
            registry=self.registry, db=self.db, business=self.business, conversation=self.conversation, lead=self.lead
        )
        self.manager = ManagerAgent(
            registry=self.registry, memory=self.memory, business=self.business, tool_router=self.router
        )
        # Register manager as well (so plan.employees == ["manager"] resolves)
        self.registry.register_employee("manager", self.manager, tools=list(self.registry.all_tools().keys()))

    def before_llm(self, message: str, history=None, delegate: bool = True):
        history = history or []
        plan = self.planner.plan(message)
        shared_memory = self.memory.shared_context(history)

        # Manager delegates to every employee named in the plan, runs their
        # tools, collects each real result, and synthesizes one reply. This
        # now does real LLM/tool work, so callers that only need plan/memory
        # (e.g. the customer-facing widget chat, which phrases its own reply)
        # can skip it with delegate=False.
        manager_result = self.manager.delegate(plan, message, history) if delegate else None

        return {
            "plan": plan,
            "memory": shared_memory.get("summary"),
            "shared_memory": shared_memory,
            "manager_result": manager_result,
        }

    def after_llm(self, reply: str) -> str:
        # Post-processing hook; currently pass-through
        return reply
