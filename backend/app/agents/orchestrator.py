from typing import Any

from app.agents.planner import Planner
from app.agents.memory import ConversationMemory
from app.agents.registry import Registry
from app.agents.tool_router import ToolRouter
from app.agents.manager_agent import ManagerAgent

# Import employee classes when available; registration is tolerant to failures
try:
    from app.agents.sales_agent import SalesAgent
except Exception:
    SalesAgent = None

try:
    from app.agents.support_agent import SupportAgent
except Exception:
    SupportAgent = None

try:
    from app.agents.receptionist_agent import ReceptionistAgent
except Exception:
    ReceptionistAgent = None

try:
    from app.agents.analytics_agent import AnalyticsAgent
except Exception:
    AnalyticsAgent = None

try:
    from app.agents.marketing_agent import MarketingAgent
except Exception:
    MarketingAgent = None

try:
    from app.agents.finance_agent import FinanceAgent
except Exception:
    FinanceAgent = None


class AIOrchestrator:
    """
    Phase 5 AI Workforce Orchestrator composing:
    Planner -> ManagerAgent -> Employees -> ToolRouter -> LLM (external)
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

        # Register tools if available (best-effort; preserves startup if module missing)
        try:
            from app.tools.lead_tool import LeadTool

            self.registry.register_tool("lead", LeadTool(db=self.db))
        except Exception:
            pass

        try:
            from app.tools.appointment_tool import AppointmentTool

            self.registry.register_tool("appointment", AppointmentTool(db=self.db))
        except Exception:
            pass

        try:
            from app.tools.quotation_tool import QuotationTool

            self.registry.register_tool("quotation", QuotationTool(db=self.db))
        except Exception:
            pass

        try:
            from app.tools.campaign_tool import CampaignTool

            self.registry.register_tool("campaign", CampaignTool(db=self.db))
        except Exception:
            pass

        try:
            from app.agents.dashboard_tools import DashboardToolDispatcher
            # Dashboard dispatcher instance for analytics
            self.registry.register_tool("dashboard", DashboardToolDispatcher(self.db, self.business))
        except Exception:
            pass

        # Instantiate employee agents and register them with allowed tools. If constructors vary, skip gracefully.
        if SalesAgent:
            try:
                sales = SalesAgent(self.business, self.lead)
                self.registry.register_employee("sales", sales, tools=["lead"])
            except Exception:
                pass

        if SupportAgent:
            try:
                support = SupportAgent(self.business, self.lead)
                self.registry.register_employee("support", support, tools=[])
            except Exception:
                pass

        if ReceptionistAgent:
            try:
                receptionist = ReceptionistAgent(self.business, self.lead)
                self.registry.register_employee("receptionist", receptionist, tools=["appointment"])
            except Exception:
                pass

        if AnalyticsAgent:
            try:
                analytics = AnalyticsAgent(self.db, self.business)
                self.registry.register_employee("analytics", analytics, tools=["dashboard"])
            except Exception:
                pass

        if MarketingAgent:
            try:
                marketing = MarketingAgent(self.business, self.lead)
                self.registry.register_employee("marketing", marketing, tools=["campaign"])
            except Exception:
                pass

        if FinanceAgent:
            try:
                finance = FinanceAgent(self.business, self.lead)
                self.registry.register_employee("finance", finance, tools=["quotation"])
            except Exception:
                pass

        # Manager gets access to all registered tools and orchestrates employees
        # Manager instance created after initial tool/employee registration
        self.router = ToolRouter(registry=self.registry, db=self.db, business=self.business, conversation=self.conversation, lead=self.lead)
        self.manager = ManagerAgent(registry=self.registry, memory=self.memory)
        # Register manager as well (manager instance for others to discover)
        self.registry.register_employee("manager", self.manager, tools=list(self.registry.all_tools().keys()))

    def before_llm(self, message: str, history=None):
        history = history or []
        plan = self.planner.plan(message)
        shared_memory = self.memory.shared_context(history)

        # Delegate to manager which will coordinate employees and build unified context
        manager_result = self.manager.delegate(plan, message, history)

        # Attempt immediate tool calls indicated by the plan (best-effort)
        immediate_tool_results = {}
        for tool_name in getattr(plan, "tools", []) or []:
            for emp in getattr(plan, "employees", []) or []:
                try:
                    res = self.router.execute(employee=emp, tool_name=tool_name, message=message)
                    immediate_tool_results.setdefault(emp, {})[tool_name] = res
                except Exception as exc:
                    immediate_tool_results.setdefault(emp, {})[tool_name] = {"success": False, "error": str(exc)}

        return {
            "plan": plan,
            "memory": shared_memory.get("summary"),
            "shared_memory": shared_memory,
            "manager_result": manager_result,
            "immediate_tool_results": immediate_tool_results,
        }

    def after_llm(self, reply: str) -> str:
        # Post-processing hook; currently pass-through
        return reply