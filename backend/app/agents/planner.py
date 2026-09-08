from dataclasses import dataclass
from typing import List


@dataclass
class Plan:
    intent: str
    confidence: float
    priority: int
    employees: List[str]
    tools: List[str]


class Planner:
    """
    Phase 5 Planner: rule-based multi-intent classifier that returns a Plan.

    - Detects sales, support, receptionist (appointments), marketing, finance, analytics, general
    - Supports multiple intents in a single message
    - Returns primary intent (highest priority), confidence, list of employees, required tools, priority
    """

    def __init__(self):
        self.intent_keywords = {
            "receptionist": [
                "appointment",
                "book",
                "schedule",
                "meeting",
                "cancel",
                "reschedule",
            ],
            "sales": [
                "price",
                "quotation",
                "quote",
                "cost",
                "buy",
                "purchase",
                "discount",
                "pricing",
                "create a lead",
                "add a lead",
                "new lead",
                "log a lead",
                "register a lead",
                "capture a lead",
            ],
            "analytics": [
                "dashboard",
                "analytics",
                "summary",
                "today",
                "revenue",
                "leads",
                "conversation",
                "chat",
                "trend",
            ],
            "marketing": [
                "instagram",
                "facebook",
                "marketing",
                "campaign",
                "caption",
                "social media post",
                "advertisement",
                "promotion",
                "promo",
            ],
            "support": [
                "problem",
                "issue",
                "error",
                "refund",
                "support",
                "help",
                "bug",
                "complaint",
                "upset",
                "unhappy",
                "angry",
                "without notice",
                "apologize",
            ],
            "finance": [
                "invoice",
                "billing",
                "quote",
                "payment",
                "refund",
                "pricing",
            ],
            # Gmail is an owner-level capability (the business's own
            # connected inbox), not a specialist persona - routes to
            # "manager" below, same as "general". See
            # ManagerAgent.respond()'s own keyword sub-routing for which
            # specific gmail_* tool (search/read/draft/send) actually
            # gets called - that finer-grained decision doesn't fit this
            # one-intent-to-one-tool-list mapping.
            "gmail": [
                "gmail",
                "email",
                "inbox",
            ],
        }

        # Which tools are typically required per employee intent
        self.intent_tools = {
            "receptionist": ["appointment"],
            "sales": ["lead"],
            "analytics": ["dashboard"],
            "marketing": ["campaign"],
            "support": [],
            "finance": ["quotation"],
            "manager": [],
            "gmail": ["gmail_search", "gmail_read", "gmail_draft", "gmail_send"],
        }

        # Lower number = higher priority
        self.intent_priority = {
            "receptionist": 10,
            "finance": 15,
            "sales": 20,
            "support": 25,
            "analytics": 30,
            "marketing": 40,
            "gmail": 45,
            "general": 50,
        }

        # Explicit intent -> employee mapping. Every intent used to
        # implicitly assume its own name was also a valid registered
        # employee name (receptionist/sales/analytics/marketing/support/
        # finance all are) - "gmail" breaks that assumption (there is no
        # "gmail" employee in the Registry, only "manager", which is
        # granted the gmail_* tools - see AIOrchestrator/ARCHITECTURE.md),
        # so it needs an explicit entry rather than relying on the
        # intent-name-equals-employee-name shortcut.
        self.intent_employee = {"gmail": "manager"}

    def plan(self, message: str) -> Plan:
        text = (message or "").lower()
        detected = set()

        for intent, keywords in self.intent_keywords.items():
            if any(k in text for k in keywords):
                detected.add(intent)

        if not detected:
            # default to manager/general
            return Plan(
                intent="general",
                confidence=0.80,
                priority=self.intent_priority["general"],
                employees=["manager"],
                tools=[],
            )

        # Map intents to employees and tools
        employees = []
        tools = []
        confidences = []

        for intent in detected:
            if intent in self.intent_employee:
                employees.append(self.intent_employee[intent])
            elif intent in self.intent_tools:
                employees.append(intent)
            else:
                employees.append("manager")
            tools.extend(self.intent_tools.get(intent, []))
            confidences.append(0.9)

        # Deduplicate while preserving order
        seen = set()
        employees_unique = []
        for e in employees:
            if e not in seen:
                seen.add(e)
                employees_unique.append(e)

        tools_unique = []
        seen_tools = set()
        for t in tools:
            if t not in seen_tools:
                seen_tools.add(t)
                tools_unique.append(t)

        # Determine primary intent by priority
        primary = min(detected, key=lambda x: self.intent_priority.get(x, 100))
        priority = self.intent_priority.get(primary, 50)
        confidence = max(confidences) if confidences else 0.8

        return Plan(
            intent=primary,
            confidence=confidence,
            priority=priority,
            employees=employees_unique,
            tools=tools_unique,
        )