import re
import time
from typing import Any, Dict, List, Optional

from app.agents.llm_reply import facts_context, generate_employee_reply
from app.agents.memory import ConversationMemory
from app.agents.registry import Registry
from app.logging_config import get_logger
from app.services.llm_client import denies_capability

logger = get_logger(__name__)

# Keyword gate for the Manager's own general-chat path (respond(), below).
# Planner already routes "gmail"/"email"/"inbox" messages to employees=
# ["manager"] (see planner.py's intent_employee mapping) - this second,
# local check picks WHICH of the four gmail_* tools that grant applies to,
# since Plan.tools is an unordered list, not a single action. Deliberately
# a plain keyword check (no LLM call) to match the rest of this class's
# philosophy of never spending a token to decide whether to call a tool.
_GMAIL_KEYWORDS = ("gmail", "email", "inbox")


def _gmail_tool_for(text: str) -> Optional[str]:
    if not any(k in text for k in _GMAIL_KEYWORDS):
        return None
    if "send" in text:
        return "gmail_send"
    if "draft" in text or "reply" in text:
        return "gmail_draft"
    if "read" in text or "open" in text:
        return "gmail_read"
    return "gmail_search"


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _strip_capability_denial_sentences(text: str) -> str:
    """Removes only the sentence(s) that deny a capability, keeping the
    rest of an employee's reply intact - e.g. "Your invoice total is $50.
    I don't have access to your Gmail though." keeps the first sentence
    and drops only the second. Deterministic, no LLM call; a naive
    sentence split can occasionally mis-split (an abbreviation, a decimal
    number) but the worst case is a slightly imperfect split, never a
    fabrication or a crash."""
    if not text:
        return text
    sentences = _SENTENCE_SPLIT_RE.split(text)
    kept = [s for s in sentences if not denies_capability(s)]
    return " ".join(kept).strip()


def _reconcile_cross_employee_capability_denials(employee_results: Dict[str, Dict[str, Any]]) -> None:
    """Relevance-aware merge fix (mutates employee_results in place):
    Planner can legitimately delegate one message to several employees at
    once (e.g. "Find emails ... invoice" matches both "finance" and
    "gmail" keywords - see planner.py). A specialist with no awareness of
    a capability outside its own role (e.g. Finance has no idea Gmail
    exists) can independently generate an honest-for-itself but system-
    wide-incorrect blanket denial ("I don't have access to your Gmail").
    _merge_replies() below just concatenates every non-empty reply, so
    that denial would sit right next to a SIBLING employee's real,
    successful answer to the exact same part of the request.

    Confirmed live: an earlier version of this function skipped an
    employee whose OWN tool result happened to succeed, on the assumption
    that meant its reply was "legitimate" and shouldn't be touched - but
    Finance's own `quotation` tool succeeded (drafted SOME text) on the
    exact real request that triggered this bug, while Finance's actual
    reply still denied Gmail access anyway (a capability with nothing to
    do with quotations) - the denial survived untouched. Whether an
    employee's own tool happened to succeed says nothing about whether a
    denial IN ITS TEXT is about that same capability, so it's not a safe
    signal to gate on. This strips a denial sentence from ANY employee's
    reply whenever ANY employee in the same turn succeeded at something -
    a real, current success elsewhere in the same answer always
    contradicts a blanket "can't do that" claim, regardless of which
    employee said it or why. Sentence-level, not whole-reply: genuine,
    relevant content (e.g. "Your invoice total is $50.") always survives
    alongside a stripped denial. Only skipped entirely when NOTHING
    succeeded this turn (nothing to reconcile against - an uncontradicted
    "I can't do that" may be an honest, correct answer)."""
    any_success = any(
        isinstance(res.get("tool_result"), dict) and res["tool_result"].get("ok") is True
        for res in employee_results.values()
    )
    if not any_success or len(employee_results) < 2:
        return

    for name, res in employee_results.items():
        original = res.get("reply") or ""
        if not denies_capability(original):
            continue
        cleaned = _strip_capability_denial_sentences(original)
        if cleaned != original.strip():
            logger.warning("manager.capability_denial_stripped_from_merge", extra={"ctx": {
                "event": "manager.capability_denial_stripped_from_merge", "employee": name,
            }})
            res["reply"] = cleaned


class ManagerAgent:
    """
    ManagerAgent: coordinates employees, delegates work, merges responses,
    resolves conflicts, and produces a unified context for the LLM.
    """

    def __init__(self, registry: Registry, memory: ConversationMemory, business: Any = None, tool_router: Any = None):
        self.registry = registry
        self.memory = memory
        self.business = business
        self.tool_router = tool_router

    @property
    def system_prompt(self) -> str:
        name = getattr(self.business, "name", None) or "the business"
        return f"""You are the Manager AI for {name}.

You coordinate a workforce of AI specialists: Sales, Receptionist, Support,
Finance, Marketing, and Analytics.

You also have direct access to the business's own connected Gmail inbox -
you can search it, read a message, create a draft reply, and send email
(sending may require the owner's approval before it actually goes out).
Only describe emails, senders, or message contents that appear in the real
tool result given to you below; if no tool result is present, or it
reports an error, say so honestly instead of guessing.

Answer general questions helpfully and concisely. Never invent business
facts, prices, or appointment slots yourself - that work belongs to the
specialist employees."""

    def respond(self, message: str, history: List[Any], tool_router: Optional[Any] = None) -> Dict[str, Any]:
        """The Manager's own reply for general chat that no specialist
        intent was detected for - including Gmail requests, since Gmail is
        an owner-level capability granted to "manager", not a specialist
        persona (see planner.py)."""
        analysis = {"memory": self.memory.shared_context(history)}
        router = tool_router or self.tool_router

        tool_result = None
        gmail_tool_name = _gmail_tool_for((message or "").lower())
        if gmail_tool_name and router is not None:
            res = router.execute(employee="manager", tool_name=gmail_tool_name, message=message)
            if res.get("success"):
                tool_result = res["result"]
            else:
                # A router-level refusal (forbidden/unknown tool) rather than
                # a Gmail-API-level failure - still real, still worth
                # grounding the reply in rather than silently dropping back
                # to tool_result=None (which is exactly how this bug looked
                # to begin with: a Gmail request answered with no Gmail
                # awareness at all).
                tool_result = {"ok": False, "error": res.get("error", "tool_error"), "message": res.get("message")}

        reply = generate_employee_reply(
            "manager", self.system_prompt, message, history,
            tool_result=tool_result, extra_context=facts_context(analysis),
        )
        return {"employee": "manager", "intent": "general", "reply": reply, "tool_result": tool_result}

    def delegate(self, plan: Any, message: str, history: List[Any]) -> Dict[str, Any]:
        """
        Delegate to one or more employees indicated in plan.employees.
        Returns a unified structure containing employee_results, final_reply, unified_context.
        """
        employee_results: Dict[str, Dict[str, Any]] = {}

        logger.info("manager.delegate", extra={"ctx": {
            "event": "manager.delegate",
            "intent": getattr(plan, "intent", None),
            "employees": list(getattr(plan, "employees", []) or ["manager"]),
        }})

        for emp in getattr(plan, "employees", []) or ["manager"]:
            employee_instance = self.registry.get_employee(emp)
            if employee_instance is None:
                logger.warning("employee.not_registered", extra={"ctx": {"event": "employee.not_registered", "employee": emp}})
                employee_results[emp] = {"reply": "", "tool_result": None, "error": "employee_not_registered"}
                continue

            # Prefer respond() (real LLM reply + real tool execution), then
            # legacy analyze()/handle() for any employee that hasn't been
            # upgraded yet.
            respond_fn = getattr(employee_instance, "respond", None)
            analyze_fn = getattr(employee_instance, "analyze", None)
            handle_fn = getattr(employee_instance, "handle", None)
            start = time.perf_counter()
            try:
                if callable(respond_fn):
                    result = respond_fn(message, history, self.tool_router)
                elif callable(analyze_fn):
                    result = analyze_fn(message, history)
                elif callable(handle_fn):
                    result = handle_fn(message=message, history=history)
                else:
                    result = {"reply": "", "tool_result": None}
                logger.info("employee.executed", extra={"ctx": {
                    "event": "employee.executed", "employee": emp,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    "success": True,
                }})
            except Exception as exc:
                logger.exception("employee.execution_failed", extra={"ctx": {
                    "event": "employee.execution_failed", "employee": emp,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    "success": False,
                }})
                result = {"reply": "", "tool_result": None, "error": str(exc)}

            # Normalize result
            if not isinstance(result, dict):
                result = {"reply": str(result), "tool_result": None}

            if "reply" not in result:
                result.setdefault("reply", "")
            if "tool_result" not in result:
                result.setdefault("tool_result", None)

            employee_results[emp] = result

        _reconcile_cross_employee_capability_denials(employee_results)
        final_reply = self._merge_replies(plan, employee_results, history)
        shared = self.memory.shared_context(history)

        unified_context = {
            "plan": plan,
            "shared_memory": shared,
            "employee_results": employee_results,
            "final_reply": final_reply,
        }

        return {
            "employee_results": employee_results,
            "final_reply": final_reply,
            "unified_context": unified_context,
        }

    def _merge_replies(self, plan: Any, employee_results: Dict[str, Dict[str, Any]], history: List[Any]) -> str:
        """
        Merge strategy:
        - Single employee: return its reply as-is.
        - Multiple employees: label each reply by employee so a multi-intent
          request (e.g. "create a lead and book an appointment") reads as one
          unified answer instead of losing either half.
        """
        replies = []
        for name, res in employee_results.items():
            txt = (res.get("reply") or "").strip()
            if txt:
                replies.append((name, txt))

        if not replies:
            return ""

        if len(replies) == 1:
            return replies[0][1]

        parts = [f"{name.capitalize()}: {txt}" for name, txt in replies]
        return "\n\n".join(parts)

    def resolve_handoff(self, from_employee: str, to_employee: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a handoff payload from one employee to another.
        """
        return {
            "from": from_employee,
            "to": to_employee,
            "context": context,
        }
