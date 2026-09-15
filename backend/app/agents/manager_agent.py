import json
import re
import time
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

from app.agents.llm_reply import facts_context, generate_employee_reply, retrieve_knowledge_context
from app.agents.memory import ConversationMemory
from app.agents.planner import GMAIL_KEYWORDS
from app.agents.registry import Registry
from app.logging_config import get_logger
from app.services.llm_client import denies_capability

logger = get_logger(__name__)

# Phase 10D: the known, fixed order to run the tool-calling real-estate
# specialists in when a single request needs more than one of them - not
# a second routing system (Planner still decides WHICH specialists a
# message needs; this only decides the ORDER a recognized chain of them
# runs in, so a later one can see an earlier one's real, structured
# findings - e.g. lead_qualifier's assessed budget/BHK feeding
# property_matcher's search). Any employee not in this list (the legacy
# single-shot employees, "manager") is unaffected - it still runs exactly
# as it always has, independently, with the raw original message.
SPECIALIST_ORDER = ["lead_qualifier", "property_matcher", "real_estate_sales", "site_visit", "customer_relations"]

# Cost/loop safety (Phase 10D): a single request must never fan out to an
# unbounded number of specialists. Bounded at the number of specialists
# that actually exist today (5) plus zero slack - Planner is a keyword
# classifier and could in principle match several intents from one
# message, but chaining more than the entire known specialist roster in
# one request is never a legitimate case, only a symptom of overly broad
# keyword matching. Each specialist's OWN MAX_TOOL_ROUNDS=4 (tool_loop.py)
# already bounds cost within a single specialist's turn; this bounds how
# many specialist turns one request can trigger.
MAX_SPECIALISTS_PER_REQUEST = len(SPECIALIST_ORDER)

_DISPLAY_NAME = {
    "lead_qualifier": "Lead Qualification",
    "property_matcher": "Property Matching",
    "real_estate_sales": "Sales Recommendation",
    "site_visit": "Site Visit",
    "customer_relations": "Customer Relations",
}


def _extract_structured_findings(tool_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Pulls each real tool call's parsed JSON result out of a
    tool-calling employee's tool_result (see
    app.agents.tool_loop.ToolCallRecord.result, threaded through by
    app.agents.tool_calling_employee.run_tool_calling_employee_turn) -
    never that employee's own natural-language reply text, so a later
    specialist in an orchestration chain sees real, structured facts
    rather than another model's prose. Keyed by tool name; a tool called
    more than once keeps only its last result (the most current one).

    `tc["result"]` is ToolRouter.execute()'s own envelope -
    {"success": bool, "result": <the tool's actual return value>} (or
    {"success": false, "error": ...} if ToolRouter itself refused/failed
    the call, e.g. "forbidden"). This unwraps that envelope one level so
    callers see the tool's own dict directly (e.g. {"success": true,
    "lead": {...}} or {"success": true, "properties": [...]}) - matching
    exactly what every tool in app/tools/ actually returns, rather than
    everything living one key deeper than every other reader of a tool
    result (ToolRouter's own tests, the tools themselves) expects."""
    if not tool_result or not isinstance(tool_result, dict):
        return {}
    findings: Dict[str, Any] = {}
    for tc in tool_result.get("tool_calls", []) or []:
        raw = tc.get("result") if isinstance(tc, dict) else None
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("result"), dict):
            parsed = parsed["result"]
        findings[tc.get("tool")] = parsed
    return findings


def _build_chain_context_message(original_message: str, prior_findings: List[tuple]) -> str:
    """Prepends the REAL structured findings of earlier specialists in an
    orchestration chain to the next specialist's message - never the
    prior specialists' full replies or raw conversation history (Phase
    10D spec: "Do not dump entire prior conversation logs blindly into
    every prompt. Use structured intermediate results."). A specialist
    with nothing structured to report (e.g. it only chatted, called no
    tool, or failed) contributes nothing here - `original_message` is
    returned unchanged when no prior specialist has real findings."""
    blocks = []
    for employee_name, findings in prior_findings:
        if findings:
            label = _DISPLAY_NAME.get(employee_name, employee_name)
            blocks.append(f"[{label} - real findings]\n{json.dumps(findings, default=str)}")
    if not blocks:
        return original_message
    return (
        f"{original_message}\n\n"
        "--- Structured context from earlier specialist(s) already run for this same request "
        "(real tool results - use these facts; re-check only if you genuinely need to verify "
        "something has not changed) ---\n" + "\n\n".join(blocks)
    )


def _approval_notes(employee_results: Dict[str, Dict[str, Any]]) -> List[str]:
    """Every Phase 10A-10C approval-proposing tool returns
    {"success": true, "proposed": true, "approval_id": ..., "status": "pending", ...}
    (see app/tools/realestate_visit_followup_tools.py) - this scans each
    specialist's real tool results for that shape and surfaces it as an
    explicit "still needs a human" note, so Manager's synthesis can never
    imply a proposed action already happened. Deterministic, zero extra
    LLM cost - reads data every approval tool already returns."""
    notes: List[str] = []
    for name, res in employee_results.items():
        findings = _extract_structured_findings(res.get("tool_result"))
        for tool_name, parsed in findings.items():
            if isinstance(parsed, dict) and parsed.get("proposed") is True and parsed.get("approval_id"):
                notes.append(
                    f"Pending human approval ({tool_name}, requested by {_DISPLAY_NAME.get(name, name)}): "
                    f"{parsed.get('message') or 'awaiting approval before this takes effect.'}"
                )
    return notes


def _verify_property_facts(employee_results: Dict[str, Dict[str, Any]], tool_router: Any) -> List[str]:
    """Phase 10D source-of-truth guarantee: never let a specialist's
    generated text (or a stale earlier tool call) be the last word on a
    property's current state. Collects every property id any specialist
    in this turn referenced in its REAL structured tool findings, then
    re-reads each one fresh via get_property (a real, zero-LLM DB read
    through the same ToolRouter permission gate) and reports its CURRENT
    status - not a diff against what anyone said, just the guaranteed-
    current fact, so live DB state always wins over anything said
    earlier in the same turn. Bounded (at most 5 distinct properties) -
    this is a synthesis safety net, not a second search feature."""
    if tool_router is None:
        return []
    property_ids: List[str] = []
    for res in employee_results.values():
        for parsed in _extract_structured_findings(res.get("tool_result")).values():
            if not isinstance(parsed, dict):
                continue
            candidates = []
            if isinstance(parsed.get("property"), dict):
                candidates.append(parsed["property"])
            for p in parsed.get("properties", []) or []:
                if isinstance(p, dict):
                    candidates.append(p)
            for c in candidates:
                pid = c.get("id")
                if pid and pid not in property_ids:
                    property_ids.append(pid)

    notes: List[str] = []
    for pid in property_ids[:5]:
        try:
            # "manager" is already granted every registered tool (see
            # AIOrchestrator.__init__) - this is Manager's OWN due-
            # diligence re-check, not attributed to whichever specialist
            # happened to look the property up earlier in the same turn.
            result = tool_router.execute(employee="manager", tool_name="get_property", message="", property_id=pid)
        except Exception:
            logger.exception("manager.property_verification_raised", extra={"ctx": {
                "event": "manager.property_verification_raised", "property_id": pid,
            }})
            continue
        # ToolRouter.execute() itself never raises for a normal tool
        # failure (it catches internally and returns success=False) - a
        # False here (tool_not_found/forbidden/execution_error, or the
        # tool's own "property_not_found") is the real, expected way this
        # can come back empty. Logged (not silently dropped) so a
        # genuinely unexpected failure here is diagnosable rather than
        # just missing from the synthesis with no trace.
        if not result.get("success"):
            logger.warning("manager.property_verification_failed", extra={"ctx": {
                "event": "manager.property_verification_failed", "property_id": pid, "error": result.get("error"),
            }})
            continue
        prop = (result.get("result") or {}).get("property")
        if not prop:
            logger.warning("manager.property_verification_not_found", extra={"ctx": {
                "event": "manager.property_verification_not_found", "property_id": pid,
                "tool_result": result.get("result"),
            }})
            continue
        notes.append(
            f"Current DB status for unit {prop.get('unit_number') or pid}: {prop.get('status')} "
            f"(price {prop.get('price')})."
        )
    return notes


def _gmail_tool_for(text: str) -> Optional[str]:
    """Keyword gate for the Manager's own general-chat path (respond(),
    below). Planner already routes GMAIL_KEYWORDS messages to employees=
    ["manager"] (see planner.py's intent_employee mapping) - this second,
    local check picks WHICH of the four gmail_* tools that grant applies
    to, since Plan.tools is an unordered list, not a single action.
    Deliberately a plain keyword check (no LLM call), and deliberately
    the SAME shared GMAIL_KEYWORDS Planner uses - these two used to be
    separately-maintained, coincidentally-identical tuples, which is
    exactly how they silently drifted apart from what real users actually
    type (neither list recognized "mail" or "message" as Gmail-relevant,
    confirmed live and via deterministic tracing)."""
    if not any(k in text for k in GMAIL_KEYWORDS):
        return None
    if "send" in text:
        return "gmail_send"
    if "draft" in text or "reply" in text:
        return "gmail_draft"
    if "read" in text or "open" in text:
        return "gmail_read"
    return "gmail_search"


def _sender_address(from_header: Optional[str]) -> Optional[str]:
    """Extracts a bare email address from a raw RFC-2822 "From" header
    value (e.g. '"Anthropic, PBC" <invoice+statements@mail.anthropic.com>')
    - stdlib email.utils.parseaddr handles the quoting/edge cases
    correctly rather than a hand-rolled regex."""
    if not from_header:
        return None
    _, addr = parseaddr(from_header)
    return addr or None


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

    def __init__(self, registry: Registry, memory: ConversationMemory, agency: Any = None, tool_router: Any = None):
        self.registry = registry
        self.memory = memory
        self.agency = agency
        self.tool_router = tool_router

    @property
    def system_prompt(self) -> str:
        name = getattr(self.agency, "name", None) or "the agency"
        return f"""You are the Manager AI for {name}.

You coordinate a workforce of AI specialists: Sales, Receptionist, Support,
Finance, Marketing, and Analytics.

You also have direct access to the agency's own connected Gmail inbox -
you can search it, read a message, create a draft reply, and send email
(sending may require the owner's approval before it actually goes out).
Only describe emails, senders, or message contents that appear in the real
tool result given to you below; if no tool result is present, or it
reports an error, say so honestly instead of guessing.

If the tool result below includes gmail_connection status, that is the
real, current, authoritative answer to any question about whether Gmail
is connected and what you're currently allowed to do with it (search and
read are always available once connected; draft depends on the current
mode; send may require the owner's approval or be fully automated) -
answer capability questions directly from that, and never claim a
capability (like automated sending) that it doesn't list as available.

Answer general questions helpfully and concisely. Never invent agency
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
        text = (message or "").lower()
        if any(k in text for k in GMAIL_KEYWORDS) and router is not None:
            tool_result = self._gmail_context(message, text, router)

        reply = generate_employee_reply(
            "manager", self.system_prompt, message, history,
            tool_result=tool_result, extra_context=facts_context(analysis),
            knowledge_context=retrieve_knowledge_context(router, "manager", message),
        )
        return {"employee": "manager", "intent": "general", "reply": reply, "tool_result": tool_result}

    def _gmail_context(self, message: str, text: str, router: Any) -> Dict[str, Any]:
        """Always fetches the real, current Gmail connection/capability
        status (gmail_status - DB-only, no real Gmail API call, no LLM
        extraction) whenever the message is Gmail-relevant at all, in
        addition to whichever specific action _gmail_tool_for() selects.

        Root cause this fixes: a pure capability question ("do you have
        access to my Gmail?") used to only ever get a tool_result when
        _gmail_tool_for()'s action-keyword guess (defaulting to
        gmail_search) happened to run - the model had no OTHER way to
        know Gmail was actually connected, and nothing stopped it from
        answering "I don't have access" from its own (wrong) assumption
        instead of real application state. Deliberately NOT trying to
        classify "is this JUST a capability question" and skip the action
        tool - that classification is exactly the kind of fragile, easy-
        to-get-wrong heuristic that would either miss real capability
        questions or wrongly skip a real action request. Both pieces of
        real information are simply always given together; the model
        (with CAPABILITY_GROUNDING_INSTRUCTION already in force - see
        llm_reply.py) answers whichever part is actually relevant."""
        status_res = router.execute(employee="manager", tool_name="gmail_status", message=message)
        if status_res.get("success"):
            connection = status_res["result"]
        else:
            connection = {"ok": False, "connected": False, "error": status_res.get("error", "tool_error")}

        action_result = None
        gmail_tool_name = _gmail_tool_for(text)
        if gmail_tool_name:
            extra_kwargs: Dict[str, Any] = {}
            if gmail_tool_name in ("gmail_draft", "gmail_send") and "@" not in message:
                # "Reply to the LATEST email" gives GmailDraftTool/
                # GmailSendTool nothing to resolve a recipient from - they
                # only ever see this raw free-text message, with no
                # automatic link to a prior search. Confirmed live and via
                # deterministic tracing: this is exactly why a real draft
                # request failed with "missing_fields" (no explicit
                # address in the message). Resolve it here with one real
                # gmail_search (empty query = Gmail's own default
                # ordering, most-recent-first, max_results=1) and thread
                # the reply's subject - never fabricated, honestly falls
                # through to the existing missing_fields failure below if
                # the search itself finds nothing or isn't connected.
                to_addr, subject = self._resolve_reply_target(router, message)
                if to_addr:
                    extra_kwargs["to"] = to_addr
                if subject:
                    extra_kwargs["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"

            action_res = router.execute(employee="manager", tool_name=gmail_tool_name, message=message, **extra_kwargs)
            if action_res.get("success"):
                action_result = action_res["result"]
            else:
                # A router-level refusal (forbidden/unknown tool) rather than
                # a Gmail-API-level failure - still real, still worth
                # grounding the reply in rather than silently dropping back
                # to tool_result=None (which is exactly how this bug looked
                # to begin with: a Gmail request answered with no Gmail
                # awareness at all).
                action_result = {"ok": False, "error": action_res.get("error", "tool_error"), "message": action_res.get("message")}

        return {
            "ok": connection.get("connected") is True,
            "gmail_connection": connection,
            "gmail_action_result": action_result,
        }

    def _resolve_reply_target(self, router: Any, message: str) -> tuple[Optional[str], Optional[str]]:
        """One real gmail_search (query="", the same "no filter" shape
        Gmail's own API already treats as its default, most-recent-first
        ordering - max_results=1) to find out who "the latest email" - the
        thing being replied to - actually is, and its subject to thread
        the reply. Returns (None, None) on any failure (not connected, no
        messages, a real search error) - never fabricated, the caller
        falls through to the existing, honest missing_fields failure."""
        try:
            search_res = router.execute(
                employee="manager", tool_name="gmail_search", message=message, query="", max_results=1,
            )
        except Exception:
            logger.exception("manager.reply_target_resolution_failed", extra={"ctx": {
                "event": "manager.reply_target_resolution_failed",
            }})
            return None, None

        if not search_res.get("success"):
            return None, None
        result = search_res.get("result")
        if not (isinstance(result, dict) and result.get("ok") and result.get("results")):
            return None, None

        latest = result["results"][0]
        return _sender_address(latest.get("from")), latest.get("subject")

    def _run_one_employee(self, emp: str, message: str, history: List[Any]) -> Dict[str, Any]:
        """Runs exactly one employee's turn (respond(), or legacy
        analyze()/handle() for anything not yet upgraded) and normalizes
        its result to the standard {"reply", "tool_result", ...} shape.
        Never raises - an employee's own exception becomes an honest
        empty-reply result with an "error" key, never a fabricated
        success (Phase 10D failure-isolation requirement)."""
        employee_instance = self.registry.get_employee(emp)
        if employee_instance is None:
            logger.warning("employee.not_registered", extra={"ctx": {"event": "employee.not_registered", "employee": emp}})
            return {"reply": "", "tool_result": None, "error": "employee_not_registered"}

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

        if not isinstance(result, dict):
            result = {"reply": str(result), "tool_result": None}
        result.setdefault("reply", "")
        result.setdefault("tool_result", None)
        return result

    def delegate(self, plan: Any, message: str, history: List[Any]) -> Dict[str, Any]:
        """
        Delegate to one or more employees indicated in plan.employees.
        Returns a unified structure containing employee_results, final_reply, unified_context.

        Phase 10D: employees in SPECIALIST_ORDER run as a single bounded,
        SEQUENTIAL chain (never more than MAX_SPECIALISTS_PER_REQUEST) -
        each one after the first receives the earlier ones' real,
        structured tool findings as extra context (never their raw
        replies or full conversation history). Every other employee in
        plan.employees (the legacy single-shot ones, "manager") runs
        exactly as it always has - independently, with the original
        message - this is purely additive for the new real-estate
        specialists, not a behavior change for anything else.
        """
        employee_results: Dict[str, Dict[str, Any]] = {}
        requested = list(getattr(plan, "employees", []) or ["manager"])

        specialist_chain = [e for e in SPECIALIST_ORDER if e in requested]
        if len(specialist_chain) > MAX_SPECIALISTS_PER_REQUEST:
            logger.warning("manager.specialist_chain_truncated", extra={"ctx": {
                "event": "manager.specialist_chain_truncated",
                "requested": specialist_chain, "max": MAX_SPECIALISTS_PER_REQUEST,
            }})
            specialist_chain = specialist_chain[:MAX_SPECIALISTS_PER_REQUEST]
        independent_employees = [e for e in requested if e not in specialist_chain]

        logger.info("manager.delegate", extra={"ctx": {
            "event": "manager.delegate",
            "intent": getattr(plan, "intent", None),
            "employees": requested,
            "specialist_chain": specialist_chain,
        }})

        # Independent employees (legacy single-shot, "manager") - unchanged.
        for emp in independent_employees:
            employee_results[emp] = self._run_one_employee(emp, message, history)

        # The bounded specialist chain - sequential, each sees prior
        # members' real structured findings.
        prior_findings: List[tuple] = []
        for emp in specialist_chain:
            emp_message = _build_chain_context_message(message, prior_findings) if prior_findings else message
            result = self._run_one_employee(emp, emp_message, history)
            employee_results[emp] = result
            prior_findings.append((emp, _extract_structured_findings(result.get("tool_result"))))

        _reconcile_cross_employee_capability_denials(employee_results)
        final_reply = self._merge_replies(plan, employee_results, history, specialist_chain=specialist_chain)
        shared = self.memory.shared_context(history)

        unified_context = {
            "plan": plan,
            "shared_memory": shared,
            "employee_results": employee_results,
            "final_reply": final_reply,
            "specialist_chain": specialist_chain,
        }

        return {
            "employee_results": employee_results,
            "final_reply": final_reply,
            "unified_context": unified_context,
        }

    def _merge_replies(
        self, plan: Any, employee_results: Dict[str, Dict[str, Any]], history: List[Any],
        specialist_chain: Optional[List[str]] = None,
    ) -> str:
        """
        Merge strategy:
        - Single employee: return its reply as-is.
        - Multiple employees: label each reply by employee so a multi-intent
          request (e.g. "create a lead and book an appointment") reads as one
          unified answer instead of losing either half.

        Phase 10D: when `specialist_chain` has 2+ members (a real
        multi-specialist orchestration, not just an incidental multi-
        intent match), chain members are ordered first (by
        SPECIALIST_ORDER, matching the narrative flow of the spec's own
        examples - qualification -> matching -> recommendation), a
        chain member that produced no reply is called out explicitly
        rather than silently dropped (never let a failed specialist's
        absence look like nothing was wrong), and the synthesis gets two
        deterministic, zero-extra-LLM-cost additions: any pending-
        approval action any specialist proposed, and a fresh, current
        DB re-check of every property any specialist's real tool results
        mentioned - live DB state always outranks anything said earlier
        in the same turn, including another specialist's own text. This
        does not change behavior at all for a single employee or for an
        incidental (non-chain) multi-intent match - both keep the exact
        pre-10D merge.
        """
        chain = specialist_chain or []
        chain_set = set(chain)
        is_real_orchestration = len(chain) >= 2

        replies = []
        missing_chain_members = []
        ordered_names = list(chain) + [n for n in employee_results if n not in chain_set]
        for name in ordered_names:
            res = employee_results.get(name)
            if res is None:
                continue
            txt = (res.get("reply") or "").strip()
            if txt:
                replies.append((name, txt))
            elif name in chain_set and is_real_orchestration:
                missing_chain_members.append(name)

        if not replies and not missing_chain_members:
            return ""

        def _label(name: str) -> str:
            return _DISPLAY_NAME.get(name, name.capitalize())

        if len(replies) == 1 and not missing_chain_members:
            return replies[0][1]

        parts = [f"{_label(name)}: {txt}" for name, txt in replies]
        for name in missing_chain_members:
            parts.append(f"{_label(name)}: Could not be completed - no result was produced, so nothing from this step is included above.")

        if is_real_orchestration:
            approval_notes = _approval_notes(employee_results)
            if approval_notes:
                parts.append("Approval needed:\n" + "\n".join(f"- {n}" for n in approval_notes))
            verification_notes = _verify_property_facts(employee_results, self.tool_router)
            if verification_notes:
                parts.append("Verified against current inventory:\n" + "\n".join(f"- {n}" for n in verification_notes))

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
