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
from app.tools.support_ticket_tool import SupportTicketTool
from app.tools.gmail_tool import GmailStatusTool, GmailSearchTool, GmailReadTool, GmailDraftTool, GmailSendTool
from app.tools.knowledge_tool import KnowledgeSearchTool


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
        self.registry.register_tool("support_ticket", SupportTicketTool(db=self.db))
        # Gmail: an owner-facing capability (the business's own connected
        # inbox), not a per-customer-conversation one - reachable through
        # the same Tool Router/permission machinery as every other tool,
        # but only "manager" is granted it below (via all_tools()), not any
        # specialist employee's fixed per-turn tool. See
        # app/tools/gmail_tool.py's module docstring for why.
        # gmail_status is DB-only (no real Gmail API call, no LLM
        # extraction) - lets Manager answer "are you connected?" from
        # real application state instead of guessing or running a
        # semantically-wrong real search just to find out.
        self.registry.register_tool("gmail_status", GmailStatusTool())
        self.registry.register_tool("gmail_search", GmailSearchTool())
        self.registry.register_tool("gmail_read", GmailReadTool())
        self.registry.register_tool("gmail_draft", GmailDraftTool())
        self.registry.register_tool("gmail_send", GmailSendTool())
        # Knowledge Base retrieval: read-only, side-effect-free, so unlike
        # Gmail it's granted to every specialist employee (not just
        # Manager) - a business's own uploaded documents are relevant
        # context for all of them, not an owner-only capability. Still a
        # DATA/RETRIEVAL layer feeding the same Planner/ToolRouter
        # pipeline, never a second AI brain - see
        # app/tools/knowledge_tool.py and ARCHITECTURE.md.
        self.registry.register_tool("knowledge_search", KnowledgeSearchTool())

        # Employee agents
        self.registry.register_employee("sales", SalesAgent(self.business, self.lead), tools=["lead", "knowledge_search"])
        self.registry.register_employee(
            "support", SupportAgent(self.business, self.lead), tools=["support_ticket", "knowledge_search"]
        )
        self.registry.register_employee(
            "receptionist", ReceptionistAgent(self.business, self.lead), tools=["appointment", "knowledge_search"]
        )
        self.registry.register_employee("analytics", AnalyticsAgent(self.business, self.lead), tools=["dashboard", "knowledge_search"])
        self.registry.register_employee("marketing", MarketingAgent(self.business, self.lead), tools=["campaign", "knowledge_search"])
        self.registry.register_employee("finance", FinanceAgent(self.business, self.lead), tools=["quotation", "knowledge_search"])

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
