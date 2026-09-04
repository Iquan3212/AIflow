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

from sqlalchemy.orm import Session

from app import models
from app.repositories.conversation_repository import (
    get_business_by_slug,
    get_conversation,
    create_conversation,
    save_message,
    load_history,
    get_business_conversations as repo_get_business_conversations,
)
from app.services.llm_client import chat_completion
from app.services.prompt_builder import build_system_prompt
from app.services.scheduling.tools import tool_definitions, ToolDispatcher
from app.services.scheduling.datetime_utils import to_local, now_utc

from app.agents.orchestrator import AIOrchestrator

MAX_TOOL_ROUNDS = 4


def get_business_conversations(db: Session, business_slug: str):
    business = get_business_by_slug(db, business_slug)
    if business is None:
        raise Exception("Business not found")

    conversations = repo_get_business_conversations(db, business.id)
    result = []
    for conversation in conversations:
        history = load_history(db, conversation.id)
        result.append({
            "id": str(conversation.id),
            "name": conversation.visitor_id,
            "phone": "",
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
    business = get_business_by_slug(db, business_slug)
    if business is None:
        raise Exception("Business not found")

    conversation = (
        get_conversation(
            db,
            conversation_id,
            business_id=business.id,
            visitor_id=visitor_id,
            channel="website",
        )
        if conversation_id
        else None
    )
    if conversation is None:
        conversation = create_conversation(db=db, business_id=business.id, visitor_id=visitor_id)

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

    Conversation Memory:
    {agent_context['memory']}
    """

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    dispatcher = ToolDispatcher(db, business, conversation, lead)
    tools = tool_definitions()

    reply_text = _run_tool_loop(
    messages,
    tools,
    dispatcher,
)

    reply_text = orchestrator.after_llm(reply_text)


    save_message(db=db, conversation_id=conversation.id, role="assistant", content=reply_text)
    return {"conversation_id": conversation.id, "reply": reply_text}


def _run_tool_loop(messages: list[dict], tools: list[dict], dispatcher: ToolDispatcher) -> str:
    """Drive the model through as many tool rounds as it needs (bounded), then
    return the final assistant text."""
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
            result = dispatcher.run(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    final = chat_completion(messages, tools=None)
    return (final.content or "").strip() or "Let me get back to you on that."
