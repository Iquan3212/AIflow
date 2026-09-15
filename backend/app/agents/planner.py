from dataclasses import dataclass
from typing import List

# Single canonical keyword list for "this message is about the agency's
# connected Gmail inbox" - shared with manager_agent.py's own
# _gmail_tool_for() gate (which decides WHICH gmail_* tool applies once
# Planner has already routed here) so the two can never drift out of sync
# again the way they silently did before: "tell me my most recent mail"
# and "find my most recent message" matched neither list ("mail" is not a
# substring of "email", and "message" wasn't present at all), so both
# Planner and Manager silently treated them as ordinary general chat -
# Gmail's tools were never even attempted, confirmed live and via
# deterministic tracing (Planner intent=general, employees=["manager"],
# Manager's own _gmail_tool_for() returning None) - not a synthesis,
# memory, or provider bug.
#
# Phase 10D: split into STRONG and WEAK signals. "gmail"/"email"/"inbox"
# essentially always mean the agency's connected inbox in this product's
# domain - always a real Gmail match. "mail" is one edge softer (kept
# strong - this product has no other "mail" concept to collide with) but
# "message" is genuinely ambiguous natural English: it's also the
# ordinary word for a customer-relations/sales draft ("draft a check-in
# message" - confirmed live, Phase 10C's smoke test routed this to
# Manager/Gmail alongside the correct customer_relations employee, purely
# because "message" is a GMAIL_KEYWORDS substring). Planner.plan() below
# only treats a WEAK-only match as the "gmail" intent when nothing more
# specific ALSO matched in the same message - preserving the original
# "find my most recent message"/"tell me my most recent mail" fix (where
# nothing else matches, so the weak signal is all there is) while no
# longer letting "message" hijack a message that's clearly about a real,
# more specific intent (site visits, customer relations, sales, etc.).
GMAIL_STRONG_KEYWORDS = ("gmail", "email", "inbox", "mail")
GMAIL_WEAK_KEYWORDS = ("message",)
GMAIL_KEYWORDS = GMAIL_STRONG_KEYWORDS + GMAIL_WEAK_KEYWORDS


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
            # Gmail is an owner-level capability (the agency's own
            # connected inbox), not a specialist persona - routes to
            # "manager" below, same as "general". See
            # ManagerAgent.respond()'s own keyword sub-routing for which
            # specific gmail_* tool (search/read/draft/send) actually
            # gets called - that finer-grained decision doesn't fit this
            # one-intent-to-one-tool-list mapping.
            "gmail": list(GMAIL_KEYWORDS),
            # Phase 10A, Step 9: new real-estate intent categories for the
            # AI workforce foundation. Deliberately routed to "manager"
            # below (intent_employee), same as "gmail" - no dedicated
            # lead_qualification/property_matching/site_visit/
            # customer_relations employee exists yet (that's 10B+), this
            # only makes Planner able to recognize and classify these
            # intents ahead of that, with zero LLM cost. Kept as
            # multi-word phrases so they don't collide with the existing
            # single-word keyword lists above.
            "lead_qualification": [
                "qualify the lead", "qualify this lead", "qualify this buyer",
                "lead qualification", "how qualified is",
                "is this lead qualified", "buying stage", "ready to buy",
            ],
            "property_matching": [
                "match a property", "matching property", "suitable property",
                "recommend a property", "which property fits", "property match",
                # Phase 10D: covers the spec's own composite-request
                # phrasing ("find three properties that fit their
                # requirements" / "find available matches") without
                # touching the existing single-property phrases above.
                "properties that fit", "find matching properties", "available matches",
                "find available matches", "matching properties",
            ],
            "site_visit": [
                "site visit", "property tour", "site tour",
                "visit the property", "visit the site", "arrange a site visit",
            ],
            "customer_relations": [
                "follow up with", "nurture the lead", "check in with the customer",
                "stay in touch with",
                # Phase 10D: covers the spec's own composite-request
                # phrasing ("summarize this buyer... since their
                # inquiry").
                "summarize this buyer", "summarize this lead", "since their inquiry",
            ],
            # Phase 10C: distinct from "sales" above (generic pricing/
            # quotation/lead-capture, any business type) - this is
            # specifically about a real-estate lead's next-best-action/
            # stalled status, routed to the new real_estate_sales
            # employee, never the legacy generic "sales" one.
            "real_estate_sales": [
                "next best action", "recommend next action", "is this lead stalled",
                "stalled lead", "sales recommendation for", "re-engage this lead",
                "should sales do next", "what should sales do",
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
            # Phase 10B: lead_qualifier/property_matcher are now real,
            # registered employees (app/agents/orchestrator.py) - see
            # intent_employee below.
            "lead_qualification": ["update_lead_qualification"],
            "property_matching": ["search_properties"],
            # Phase 10C: site_visit/customer_relations/real_estate_sales
            # are now real, registered employees too, and each employee
            # name matches its intent name exactly (like receptionist/
            # sales/finance/etc.), so no intent_employee entry is needed
            # for any of these three - the shortcut below handles it.
            "site_visit": ["propose_visit"],
            "customer_relations": ["draft_customer_message"],
            "real_estate_sales": ["update_lead_qualification"],
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
            "site_visit": 12,
            "lead_qualification": 22,
            "property_matching": 23,
            "real_estate_sales": 24,
            "customer_relations": 42,
            "general": 50,
        }

        # Explicit intent -> employee mapping, needed ONLY when the
        # intent name doesn't match the real registered employee name.
        # "gmail" has no "gmail" employee (routes to "manager", granted
        # the gmail_* tools). lead_qualification/property_matching route
        # to lead_qualifier/property_matcher (Phase 10B) - different
        # names by design (see those employees' own modules).
        # site_visit/customer_relations/real_estate_sales (Phase 10C) all
        # use the intent-name-equals-employee-name shortcut instead - see
        # app/agents/site_visit_agent.py, customer_relations_agent.py,
        # real_estate_sales_agent.py's EMPLOYEE_NAME constants.
        self.intent_employee = {
            "gmail": "manager",
            "lead_qualification": "lead_qualifier",
            "property_matching": "property_matcher",
        }

    def plan(self, message: str) -> Plan:
        text = (message or "").lower()
        detected = set()

        for intent, keywords in self.intent_keywords.items():
            if intent == "gmail":
                continue  # decided separately below - see GMAIL_STRONG/WEAK_KEYWORDS
            if any(k in text for k in keywords):
                detected.add(intent)

        # A STRONG signal ("gmail"/"email"/"inbox"/"mail") always means
        # Gmail. A WEAK-only signal ("message") is genuinely ambiguous
        # with ordinary real-estate/CRM language ("draft a ... message"
        # for a lead) - only treated as the "gmail" intent when nothing
        # more specific already matched; a strong signal always wins
        # regardless of what else matched (the original multi-intent
        # collision fix - see test_planner_gmail_multi_intent.py).
        if any(k in text for k in GMAIL_STRONG_KEYWORDS):
            detected.add("gmail")
        elif any(k in text for k in GMAIL_WEAK_KEYWORDS) and not detected:
            detected.add("gmail")

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