"""
Phase 10B, Part 2: the Property Matching AI employee - a real employee
inside the existing AI Workforce architecture (registered in Registry,
reachable through the existing Planner -> ManagerAgent.delegate() path,
executing through the existing bounded tool-calling loop and ToolRouter
permission gate; see app/agents/orchestrator.py's registration). No
second agent framework, no second RAG mechanism.

Grants only the read-only property/project tools (Phase 10A) -
search_properties, search_projects, get_property, knowledge_search. It
cannot update leads, propose visits, or touch any commercial state -
this employee only searches and explains real inventory.
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.agents.llm_reply import knowledge_context_messages, retrieve_knowledge_context
from app.agents.tool_calling_employee import normalize_history_messages, run_tool_calling_employee_turn

EMPLOYEE_NAME = "property_matcher"

GRANTED_TOOLS = ["search_properties", "search_projects", "get_property", "knowledge_search"]


class PropertyMatcherAgent:
    """
    AI Workforce - Property Matching Employee

    Responsibilities (Phase 10B spec): interpret a buyer's requirements
    (budget, BHK, locality, project, property type, area, furnishing,
    possession, amenities) and match them against REAL inventory via
    search_properties/search_projects/get_property - never recommend a
    property from language-model knowledge alone. A typical model-
    selected flow: search_properties -> get_property on shortlisted
    candidates -> a ranked, explained recommendation grounded entirely
    in what those tools actually returned.
    """

    def __init__(self, agency: Any, lead: Any = None):
        self.agency = agency
        self.lead = lead

    @property
    def system_prompt(self) -> str:
        name = getattr(self.agency, "name", None) or "the agency"
        return f"""You are the Property Matching AI for {name}.

ROLE

You match a buyer's stated requirements against this agency's REAL
inventory. You never recommend a property that isn't a real result
from search_properties or get_property.

HOW TO WORK

1. Identify the requirements actually stated (budget, BHK, locality,
   project, property type, area, furnishing, possession, amenities) -
   never invent a requirement that wasn't mentioned.
2. Call search_properties with the filters you can determine. Do not
   assume every fact fits in one call - inspect the results, and call
   get_property on shortlisted candidates for full detail before
   recommending them.
3. Explain match quality honestly, from the real fields returned:
   - Hard filters: never recommend a property whose real status is not
     available/active; never recommend a unit whose BHK clearly
     contradicts an explicit requirement; be honest, not evasive, about
     a clearly incompatible budget.
   - Soft matching: location, budget fit, area, amenities, project
     preference, furnishing, possession preference.

SOURCE OF TRUTH

Structured database facts (from search_properties/get_property) are
always authoritative over anything else, including any agency
knowledge-base content given to you below. If a knowledge-base document
says a unit is "available" but the actual property_status result says
otherwise, the database result wins - say so plainly rather than
repeating the stale document text. If no real property matches, say
that honestly instead of inventing one.

Never invent a property, price, availability, BHK, area, or project
that did not come from a real tool result.

Always remain concise and professional."""

    def respond(self, message: str, history: List[Any], tool_router: Optional[Any] = None) -> dict:
        if tool_router is None:
            return {"employee": EMPLOYEE_NAME, "intent": "property_matching", "reply": "", "tool_result": None, "error": "no_tool_router"}

        knowledge_context = retrieve_knowledge_context(tool_router, EMPLOYEE_NAME, message)
        extra_system_messages = knowledge_context_messages(knowledge_context)

        result = run_tool_calling_employee_turn(
            tool_router.registry, EMPLOYEE_NAME,
            db=tool_router.db, agency=tool_router.agency, conversation=tool_router.conversation, lead=tool_router.lead,
            system_prompt=self.system_prompt, history=normalize_history_messages(history), message=message,
            extra_system_messages=extra_system_messages,
        )

        return {
            "employee": EMPLOYEE_NAME,
            "intent": "property_matching",
            "reply": result.reply,
            "tool_result": {
                "ok": result.terminated_reason != "provider_error",
                "terminated_reason": result.terminated_reason,
                "tool_calls": [{"tool": tc.tool, "args": tc.args, "ok": tc.ok, "result": tc.result} for tc in result.tool_calls],
            },
        }
