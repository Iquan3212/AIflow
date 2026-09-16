"""
Registered workflow action executors (Step 8/22): every action type a
Workflow can configure maps to exactly one function here, and every one
of those functions calls a REAL, EXISTING service this app already uses
elsewhere (GmailService, NotificationDispatcher) - never a second
implementation of Gmail or notification logic, never arbitrary code,
never a raw SQL/HTTP/shell escape hatch. `execute_action()` is the single
entrypoint the engine calls; an action_type not in ACTION_EXECUTORS is a
real error, not a silent no-op.

Every executor is deterministic and LLM-free: any text it sends (a
notification body, a Gmail draft/send body) is built by safe, literal
string substitution against the workflow's OWN configured template and
the trigger's structured data - never a model call, so a workflow's
per-execution behavior is fully predictable and testable without an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.logging_config import get_logger
from app.services.gmail.gmail_service import GmailService
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.notifications import preferences as notif_prefs
from app.services.workflows.config import (
    ACTION_CREATE_GMAIL_DRAFT,
    ACTION_REQUEST_APPROVAL,
    ACTION_RUN_AI_SPECIALIST,
    ACTION_SEND_GMAIL,
    ACTION_SEND_NOTIFICATION,
)

logger = get_logger(__name__)


class _SafeDict(dict):
    """Used with str.format_map() so a template referencing a field this
    trigger's data doesn't have renders as an empty string, never a
    KeyError that would crash the whole workflow run over a cosmetic
    template mismatch."""

    def __missing__(self, key):
        return ""


def render_template(template: str, trigger_data: dict) -> str:
    """Flattens trigger_data's one level of nesting (e.g. {"lead":
    {"name": "Priya"}} -> {"lead_name": "Priya"}) and substitutes into
    `template` via str.format_map - plain, literal, deterministic string
    substitution, never an LLM call and never Python's eval/exec."""
    flat: dict[str, Any] = {}
    for root, sub in (trigger_data or {}).items():
        if isinstance(sub, dict):
            for k, v in sub.items():
                flat[f"{root}_{k}"] = "" if v is None else v
        else:
            flat[root] = sub
    return (template or "").format_map(_SafeDict(flat))


def resolve_field(trigger_data: dict, field: str):
    parts = (field or "").split(".", 1)
    if len(parts) != 2:
        return None
    root, key = parts
    return (trigger_data.get(root) or {}).get(key)


@dataclass
class ActionOutcome:
    status: str  # "succeeded" | "failed" | "waiting_approval" - a WorkflowStepStatus value
    result: dict | None = None
    error: str | None = None
    gmail_pending_action_id: str | None = None


def _action_send_notification(db: Session, agency: models.Agency, trigger_data: dict, config: dict) -> ActionOutcome:
    """Reuses NotificationDispatcher exactly as every other trigger site
    in this app already does (Step 20: existing notification preferences
    remain authoritative - is_enabled() is checked INSIDE the dispatcher,
    the same single source of truth every other event already goes
    through; a disabled preference makes this a real, honest no-op, never
    bypassed because a workflow asked for it)."""
    audience = config.get("audience", "owner")
    event_type = config.get("event_type")
    if event_type not in notif_prefs.ALL_EVENTS:
        return ActionOutcome(status="failed", error=f"Unknown notification event_type: {event_type!r}")

    subject = render_template(config.get("subject", ""), trigger_data)
    body = render_template(config.get("body_template", ""), trigger_data)
    dispatcher = NotificationDispatcher()

    if audience == "owner":
        results = dispatcher.notify_owner(db=db, agency=agency, event_type=event_type, subject=subject, body=body)
    elif audience == "customer":
        name = resolve_field(trigger_data, config.get("name_field", ""))
        email = resolve_field(trigger_data, config.get("email_field", ""))
        phone = resolve_field(trigger_data, config.get("phone_field", ""))
        if not (email or phone):
            return ActionOutcome(status="failed", error="No customer email or phone available in trigger data.")
        results = dispatcher.notify_customer(
            db=db, agency_id=agency.id, event_type=event_type,
            name=name, email=email, phone=phone, subject=subject, body=body,
        )
    else:
        return ActionOutcome(status="failed", error=f"Unknown notification audience: {audience!r}")

    sent_channels = [r.channel for r in results if getattr(r, "ok", False)]
    return ActionOutcome(status="succeeded", result={"sent_channels": sent_channels, "audience": audience})


def _resolve_gmail_target(trigger_data: dict, config: dict) -> tuple[str | None, str | None]:
    to = config.get("to")
    if not to and config.get("to_field"):
        to = resolve_field(trigger_data, config["to_field"])
    subject = render_template(config.get("subject", ""), trigger_data)
    return to, subject


def _action_create_gmail_draft(db: Session, agency: models.Agency, trigger_data: dict, config: dict) -> ActionOutcome:
    """Reuses GmailService.draft() exactly - a draft is always safe/
    immediate under this app's existing Gmail design (Step 18: never
    bypass Gmail OAuth/connection checks/send mode/approval; draft never
    needed approval before Phase 5 either, so nothing changes here)."""
    to, subject = _resolve_gmail_target(trigger_data, config)
    if not to:
        return ActionOutcome(status="failed", error="No recipient email address available for this action.")
    body = render_template(config.get("body_template", ""), trigger_data)

    result = GmailService(db).draft(agency, to=to, subject=subject, body=body, employee="workflow")
    if not result.get("ok"):
        return ActionOutcome(status="failed", error=result.get("message") or result.get("error") or "Gmail draft failed.")
    return ActionOutcome(status="succeeded", result={"to": to, "subject": subject})


def _action_send_gmail(db: Session, agency: models.Agency, trigger_data: dict, config: dict) -> ActionOutcome:
    """Reuses GmailService.send() exactly - the agency's OWN existing
    send_mode (read_only/approval_required/automated) is the ONLY thing
    that decides whether this sends immediately, queues a real
    GmailPendingAction for approval, or is refused outright. A workflow
    can NEVER turn an approval_required agency into an automatic-send
    one (Step 9/18) - this function has no code path that skips that
    check; it is the exact same GmailService every chat-driven Gmail
    action already goes through."""
    to, subject = _resolve_gmail_target(trigger_data, config)
    if not to:
        return ActionOutcome(status="failed", error="No recipient email address available for this action.")
    body = render_template(config.get("body_template", ""), trigger_data)

    result = GmailService(db).send(agency, to=to, subject=subject, body=body, employee="workflow")
    if not result.get("ok"):
        return ActionOutcome(status="failed", error=result.get("message") or result.get("error") or "Gmail send failed.")
    if result.get("queued_for_approval"):
        return ActionOutcome(
            status="waiting_approval",
            result={"to": to, "subject": subject, "queued_for_approval": True},
            gmail_pending_action_id=result.get("pending_action_id"),
        )
    return ActionOutcome(status="succeeded", result={"to": to, "subject": subject, "sent": True})


def _action_request_approval(db: Session, agency: models.Agency, trigger_data: dict, config: dict) -> ActionOutcome:
    """A pure approval gate with no side effect of its own - useful
    standalone (e.g. "flag this lead for owner review") or as an explicit
    step before a later action. Approving it just marks the step
    succeeded (see engine.py); nothing else happens."""
    return ActionOutcome(status="waiting_approval", result={"note": "Awaiting explicit owner approval."})


def _action_run_ai_specialist(db: Session, agency: models.Agency, trigger_data: dict, config: dict) -> ActionOutcome:
    """Phase 11: runs exactly ONE bounded turn of one existing real-estate
    AI Workforce specialist (Phase 10B/10C) through the SAME
    ManagerAgent/Registry/ToolRouter pipeline every other AI Workforce
    call already goes through - never a second AI brain, never a
    specialist chain/loop here (that bounded-chain behavior is
    ManagerAgent.delegate()'s own concern for a live chat turn; a
    workflow action runs one specialist, one turn, deterministically).

    Never bypasses AIActionApproval: whatever the specialist's own tools
    do (e.g. update_lead_qualification writes directly, since it never
    touches commercial state; a site-visit/booking-affecting tool
    proposes via AIActionApproval instead - see each tool's own
    docstring) happens exactly as it would in a live chat turn. This
    executor only runs the turn and records its real, structured
    result - it never itself confirms/cancels a booking or appointment,
    and never sends anything on its own.

    A workflow author can additionally set this action's own
    `requires_approval: true` (engine.py's existing generic
    ApprovalRequest gate, unrelated to AIActionApproval) to require a
    human decision before the specialist is even allowed to run at all -
    no new gating code needed for that; it already works for any action
    type.
    """
    # Lazy import: keeps this module's top-level import surface limited
    # to what every OTHER action already needs (Gmail/notifications), and
    # avoids the AI Workforce agent stack loading for every unrelated
    # action type. Confirmed no import cycle: app/agents/* never imports
    # app.services.workflows.
    from app.agents.manager_agent import SPECIALIST_ORDER
    from app.agents.orchestrator import AIOrchestrator

    specialist = config.get("specialist")
    if specialist not in SPECIALIST_ORDER:
        return ActionOutcome(
            status="failed",
            error=f"Unknown or unsupported specialist: {specialist!r}. Must be one of {list(SPECIALIST_ORDER)}.",
        )

    message = render_template(config.get("message_template", ""), trigger_data)
    if not message.strip():
        return ActionOutcome(status="failed", error="No message_template configured for this action.")

    lead_id_field = config.get("lead_id_field", "lead.id")
    lead_id = resolve_field(trigger_data, lead_id_field)
    lead = None
    if lead_id:
        lead = (
            db.query(models.Lead)
            .filter(models.Lead.id == lead_id, models.Lead.agency_id == agency.id)
            .first()
        )
        if lead is None:
            return ActionOutcome(status="failed", error=f"No lead {lead_id!r} found for this agency.")

    orchestrator = AIOrchestrator(db, agency, conversation=None, lead=lead)
    result = orchestrator.manager._run_one_employee(specialist, message, history=[])

    if result.get("error"):
        return ActionOutcome(status="failed", error=f"{specialist} failed: {result['error']}")

    return ActionOutcome(status="succeeded", result={
        "specialist": specialist,
        "reply": result.get("reply"),
        "tool_result": result.get("tool_result"),
    })


ACTION_EXECUTORS = {
    ACTION_SEND_NOTIFICATION: _action_send_notification,
    ACTION_CREATE_GMAIL_DRAFT: _action_create_gmail_draft,
    ACTION_SEND_GMAIL: _action_send_gmail,
    ACTION_REQUEST_APPROVAL: _action_request_approval,
    ACTION_RUN_AI_SPECIALIST: _action_run_ai_specialist,
}


def execute_action(action_type: str, db: Session, agency: models.Agency, trigger_data: dict, config: dict) -> ActionOutcome:
    executor = ACTION_EXECUTORS.get(action_type)
    if executor is None:
        return ActionOutcome(status="failed", error=f"Unregistered action type: {action_type!r}")
    try:
        return executor(db, agency, trigger_data, config)
    except Exception as exc:
        logger.exception("workflow.action_executor_error", extra={"ctx": {
            "event": "workflow.action_executor_error", "action_type": action_type, "agency_id": agency.id,
        }})
        return ActionOutcome(status="failed", error=f"Unexpected error running {action_type}: {exc}")
