"""
Conversation orchestration for the website widget / chat channel.

One customer message == one tool-calling turn:
  1. persist the incoming message
  2. get-or-create the lead for this conversation
  3. ask the model, exposing the receptionist tools (lead capture + booking)
  4. run any tool calls, feed results back, let the model phrase the reply
  5. persist and return the reply

This replaces the previous design that fired two extra extraction completions
(lead + appointment) on every message before the real reply — three LLM calls
per message became one turn, and booking now goes through validated availability
logic instead of free-text date strings.
"""

import json
import time

from sqlalchemy.orm import Session

from app import models
from app.repositories.conversation_repository import (
    get_business_by_slug,
    get_conversation,
    find_conversation_by_visitor,
    create_conversation,
    save_message,
    load_history,
    get_business_conversations as repo_get_business_conversations,
)
from app.services.llm_client import (
    chat_completion,
    LLMProviderError,
    NO_TOOL_CALL_INSTRUCTION,
    format_tool_result_for_prompt,
)
from app.services.prompt_builder import build_system_prompt
from app.services.scheduling.tools import tool_definitions, ToolDispatcher
from app.services.scheduling.datetime_utils import to_local, now_utc

from app.agents.orchestrator import AIOrchestrator
from app.agents.prompt_guard import (
    wrap_untrusted,
    detect_injection_signals,
    INJECTION_REINFORCEMENT,
    leaks_system_prompt,
    SAFE_FALLBACK_REPLY,
    is_fallback_reply,
)
from app.logging_config import get_logger

logger = get_logger(__name__)

MAX_TOOL_ROUNDS = 4


def get_business_conversations(db: Session, business_slug: str):
    """Every real customer conversation, on any channel (website, WhatsApp,
    Instagram). The business's own internal Manager AI conversation
    (channel="employee", visitor_id="dashboard-owner" - see
    get_or_create_employee_conversation) has its own dedicated page (Manager
    AI) and must never show up here impersonating a customer - that was a
    real bug: this inbox is customer-facing, and mixing in the owner's own
    testing conversation made every metric here wrong for it. Filtering by
    excluding "employee" rather than only including "website" is what lets
    a newly connected channel show up here automatically, with no change
    needed here when one is added."""
    business = get_business_by_slug(db, business_slug)
    if business is None:
        raise Exception("Business not found")

    conversations = [
        c for c in repo_get_business_conversations(db, business.id)
        if c.channel != "employee"
    ]
    result = []
    for conversation in conversations:
        history = load_history(db, conversation.id)
        # Customer identity lives on the linked Lead, not the anonymous
        # visitor_id - that was the other real bug (name/phone were either
        # the raw visitor_id or a hardcoded empty string, never the actual
        # customer info captured mid-conversation).
        lead = conversation.lead
        customer_name = lead.name if lead and lead.name else None
        last_message = history[-1] if history else None
        result.append({
            "id": str(conversation.id),
            "channel": conversation.channel,
            "customer_name": customer_name,
            # Backward-compatible display label: real name once captured,
            # otherwise a plain, honest label - not a truncated fragment of
            # the internal visitor_id, which reads as meaningless noise.
            "name": customer_name or "Anonymous visitor",
            "phone": (lead.phone if lead else None) or "",
            "total_messages": len(history),
            "last_message": last_message.content if last_message else None,
            "created_at": conversation.started_at.isoformat() if conversation.started_at else None,
            "updated_at": (
                last_message.created_at if last_message else conversation.started_at
            ).isoformat() if (last_message or conversation.started_at) else None,
            "messages": [
                {"sender": "user" if msg.role == "user" else "ai", "text": msg.content}
                for msg in history
            ],
        })
    return result


def _get_or_create_lead(db: Session, business_id: str, conversation_id: str) -> models.Lead:
    lead = (
        db.query(models.Lead)
        .filter(models.Lead.business_id == business_id,
                models.Lead.conversation_id == conversation_id)
        .first()
    )
    if lead is None:
        lead = models.Lead(business_id=business_id, conversation_id=conversation_id, status="new")
        db.add(lead)
        db.commit()
        db.refresh(lead)
    return lead


def _scheduling_context(business) -> str:
    local = to_local(now_utc(), business.timezone)
    return (
        f"CURRENT DATE AND TIME: {local.strftime('%A, %d %B %Y, %I:%M %p')} "
        f"({business.timezone}).\n"
        f"When booking, all times are in this timezone."
    )


def process_message(
    db: Session,
    business_slug: str,
    visitor_id: str,
    conversation_id: str | None,
    message: str,
):
    """The website widget's entrypoint: resolves the business by its public
    slug (the one identifier the widget's <script> tag actually knows), then
    hands off to the channel-agnostic core. Unchanged in behavior from
    before WhatsApp/Instagram existed - this is exactly the same function
    signature and logic that's always powered the widget."""
    business = get_business_by_slug(db, business_slug)
    if business is None:
        raise Exception("Business not found")

    return process_message_for_business(
        db, business=business, visitor_id=visitor_id,
        conversation_id=conversation_id, message=message, channel="website",
    )


def process_message_for_business(
    db: Session,
    business,
    visitor_id: str,
    conversation_id: str | None,
    message: str,
    channel: str = "website",
):
    """Channel-agnostic core: one message in, one persisted reply out,
    regardless of whether it arrived via the website widget, a WhatsApp
    webhook, or an Instagram DM webhook. Takes an already-resolved
    `business` because each channel identifies the business a different way
    (the widget by its public slug; a Meta webhook by which of the
    business's connected phone numbers/IG accounts received the message -
    see services/channels/). `visitor_id` is whatever identifies the same
    customer across their messages on this channel (a browser-generated
    UUID for the widget, a phone number for WhatsApp, an IG-scoped sender
    id for Instagram) - conversation reuse, lead capture, booking, and the
    full AI Workforce tool set behave identically no matter which channel
    this came from. This is the one and only place a customer message
    reaches the LLM - there is no separate WhatsApp/Instagram AI logic."""
    if conversation_id:
        conversation = get_conversation(
            db, conversation_id, business_id=business.id, visitor_id=visitor_id, channel=channel,
        )
    else:
        # No caller-remembered id (every webhook channel; a website
        # visitor's very first-ever message) - fall back to this visitor's
        # own existing conversation on this channel before starting a new
        # one, so a phone number/IG account texting again reuses its
        # thread instead of losing history on every message.
        conversation = find_conversation_by_visitor(db, business.id, visitor_id, channel)

    if conversation is None:
        conversation = create_conversation(db=db, business_id=business.id, visitor_id=visitor_id, channel=channel)

    save_message(db=db, conversation_id=conversation.id, role="user", content=message)

    lead = _get_or_create_lead(db, business.id, conversation.id)
    orchestrator = AIOrchestrator(db=db,business=business,conversation=conversation,lead=lead,)

    history = load_history(db, conversation.id)
    agent_context = orchestrator.before_llm(message, history, delegate=False)

    config = business.chatbot_config
    system_prompt = build_system_prompt(
        business=business,
        config=config,
        lead=lead,
        buying_intent=True,  # tool-gated now; the model decides when to collect/book
        scheduling_context=_scheduling_context(business),
    )
    system_prompt += f"""

    AI ORCHESTRATOR

    Detected Intent:
    {agent_context['plan'].intent}

    {wrap_untrusted("CONVERSATION MEMORY", agent_context['memory'])}
    """

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        # A prior turn's provider-error/leak-backstop apology (see
        # prompt_guard.is_fallback_reply) is this app's own failure text,
        # never real assistant content - replaying it here would show the
        # model its own past excuse as if it had actually said that.
        if msg.role == "assistant" and is_fallback_reply(msg.content):
            continue
        messages.append({"role": msg.role, "content": msg.content})

    # The heuristic only ever adds a reminder - it never blocks, refuses, or
    # changes what gets sent to the model otherwise. See prompt_guard.py.
    if detect_injection_signals(message):
        messages.append({"role": "system", "content": INJECTION_REINFORCEMENT})

    dispatcher = ToolDispatcher(db, business, conversation, lead)
    tools = tool_definitions()

    reply_text = _run_tool_loop(
    messages,
    tools,
    dispatcher,
    channel,
)

    # Backstop: even if the model was talked into reciting its instructions
    # despite the guard rules baked into system_prompt, never let that leave
    # this function.
    if leaks_system_prompt(reply_text, system_prompt):
        logger.warning("prompt_guard.leak_detected", extra={"ctx": {"event": "prompt_guard.leak_detected", "channel": channel}})
        reply_text = SAFE_FALLBACK_REPLY

    reply_text = orchestrator.after_llm(reply_text)


    save_message(db=db, conversation_id=conversation.id, role="assistant", content=reply_text)
    return {"conversation_id": conversation.id, "reply": reply_text}


def _run_tool_loop(messages: list[dict], tools: list[dict], dispatcher: ToolDispatcher, channel: str = "website") -> str:
    """Drive the model through as many tool rounds as it needs (bounded), then
    return the final assistant text.

    A real website visitor must never see a raw 500/"Internal Server
    Error" just because the LLM provider is rate-limited or temporarily
    down - that's not something they caused or can fix by reloading, and
    the chat widget should degrade the same way the Manager AI path
    already does: a real, honest chat-style reply explaining the AI is
    temporarily unavailable, not a generic server error. LLMProviderError
    carries a message classified by actual cause (rate limit vs. provider
    outage vs. something else) - see llm_client.py."""
    # Raw dispatcher.run() outputs from this turn - kept so a real,
    # successful action isn't lost if final synthesis (below) fails or
    # comes back unusable; see _deterministic_fallback_reply().
    tool_results_this_turn: list[str] = []
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            msg = chat_completion(messages, tools=tools, tool_choice="auto")
            tool_calls = getattr(msg, "tool_calls", None)

            if not tool_calls:
                return (msg.content or "").strip() or "Sorry, could you say that again?"

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            })
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                start = time.perf_counter()
                result = dispatcher.run(tc.function.name, args)
                tool_results_this_turn.append(result)
                logger.info("tool.executed", extra={"ctx": {
                    "event": "tool.executed", "tool": tc.function.name, "channel": channel,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                }})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        # No more tool rounds are allowed past this point (tools=None) - the
        # same structural shape as llm_reply.py's own final synthesis call,
        # so it carries the same safety instruction and low, deterministic
        # temperature rather than a Gmail/tool-specific fix. The in-loop
        # calls above (which DO offer tools) are untouched.
        messages.append({"role": "system", "content": NO_TOOL_CALL_INSTRUCTION})
        try:
            final = chat_completion(messages, tools=None, temperature=0)
        except LLMProviderError as exc:
            # Only THIS final call is special-cased (never the in-loop
            # calls above, which still propagate to the outer except) -
            # real tool results were already gathered this turn and must
            # not be discarded just because phrasing them failed.
            logger.warning("conversation.final_synthesis_failed", extra={"ctx": {
                "event": "conversation.final_synthesis_failed", "channel": channel, "error_reason": exc.reason,
            }})
            return _deterministic_fallback_reply(tool_results_this_turn) or exc.user_message

        if not (final.content or "").strip() and final.tool_calls:
            logger.warning("conversation.unexpected_tool_call_in_synthesis", extra={"ctx": {
                "event": "conversation.unexpected_tool_call_in_synthesis", "channel": channel,
            }})
        text = (final.content or "").strip()
        if text:
            return text
        return _deterministic_fallback_reply(tool_results_this_turn) or "Let me get back to you on that."
    except LLMProviderError as exc:
        logger.warning("conversation.llm_provider_error", extra={"ctx": {
            "event": "conversation.llm_provider_error", "channel": channel, "error_reason": exc.reason,
        }})
        return exc.user_message


def _deterministic_fallback_reply(raw_tool_results: list[str]) -> str | None:
    """Zero-LLM, code-generated summary of this turn's real tool results -
    used only when final synthesis itself fails or comes back empty/
    unusable. Never invents data: each entry is exactly what
    ToolDispatcher.run() actually returned (a JSON string per tool - see
    app/services/scheduling/tools.py), mechanically reformatted, never
    reworded or embellished. Returns None (not a fabricated placeholder)
    when there's nothing real to show, so the caller falls back to its own
    honest generic message instead."""
    if not raw_tool_results:
        return None
    parts = []
    for raw in raw_tool_results:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            data = raw
        parts.append(format_tool_result_for_prompt(data) if isinstance(data, (dict, list)) else str(data))
    return "Here's what I found:\n\n" + "\n\n".join(parts)
