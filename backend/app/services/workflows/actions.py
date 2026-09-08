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


def _action_send_notification(db: Session, business: models.Business, trigger_data: dict, config: dict) -> ActionOutcome:
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
        results = dispatcher.notify_owner(db=db, business=business, event_type=event_type, subject=subject, body=body)
    elif audience == "customer":
        name = resolve_field(trigger_data, config.get("name_field", ""))
        email = resolve_field(trigger_data, config.get("email_field", ""))
        phone = resolve_field(trigger_data, config.get("phone_field", ""))
        if not (email or phone):
            return ActionOutcome(status="failed", error="No customer email or phone available in trigger data.")
        results = dispatcher.notify_customer(
            db=db, business_id=business.id, event_type=event_type,
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


def _action_create_gmail_draft(db: Session, business: models.Business, trigger_data: dict, config: dict) -> ActionOutcome:
    """Reuses GmailService.draft() exactly - a draft is always safe/
    immediate under this app's existing Gmail design (Step 18: never
    bypass Gmail OAuth/connection checks/send mode/approval; draft never
    needed approval before Phase 5 either, so nothing changes here)."""
    to, subject = _resolve_gmail_target(trigger_data, config)
    if not to:
        return ActionOutcome(status="failed", error="No recipient email address available for this action.")
    body = render_template(config.get("body_template", ""), trigger_data)

    result = GmailService(db).draft(business, to=to, subject=subject, body=body, employee="workflow")
    if not result.get("ok"):
        return ActionOutcome(status="failed", error=result.get("message") or result.get("error") or "Gmail draft failed.")
    return ActionOutcome(status="succeeded", result={"to": to, "subject": subject})


def _action_send_gmail(db: Session, business: models.Business, trigger_data: dict, config: dict) -> ActionOutcome:
    """Reuses GmailService.send() exactly - the business's OWN existing
    send_mode (read_only/approval_required/automated) is the ONLY thing
    that decides whether this sends immediately, queues a real
    GmailPendingAction for approval, or is refused outright. A workflow
    can NEVER turn an approval_required business into an automatic-send
    one (Step 9/18) - this function has no code path that skips that
    check; it is the exact same GmailService every chat-driven Gmail
    action already goes through."""
    to, subject = _resolve_gmail_target(trigger_data, config)
    if not to:
        return ActionOutcome(status="failed", error="No recipient email address available for this action.")
    body = render_template(config.get("body_template", ""), trigger_data)

    result = GmailService(db).send(business, to=to, subject=subject, body=body, employee="workflow")
    if not result.get("ok"):
        return ActionOutcome(status="failed", error=result.get("message") or result.get("error") or "Gmail send failed.")
    if result.get("queued_for_approval"):
        return ActionOutcome(
            status="waiting_approval",
            result={"to": to, "subject": subject, "queued_for_approval": True},
            gmail_pending_action_id=result.get("pending_action_id"),
        )
    return ActionOutcome(status="succeeded", result={"to": to, "subject": subject, "sent": True})


def _action_request_approval(db: Session, business: models.Business, trigger_data: dict, config: dict) -> ActionOutcome:
    """A pure approval gate with no side effect of its own - useful
    standalone (e.g. "flag this lead for owner review") or as an explicit
    step before a later action. Approving it just marks the step
    succeeded (see engine.py); nothing else happens."""
    return ActionOutcome(status="waiting_approval", result={"note": "Awaiting explicit owner approval."})


ACTION_EXECUTORS = {
    ACTION_SEND_NOTIFICATION: _action_send_notification,
    ACTION_CREATE_GMAIL_DRAFT: _action_create_gmail_draft,
    ACTION_SEND_GMAIL: _action_send_gmail,
    ACTION_REQUEST_APPROVAL: _action_request_approval,
}


def execute_action(action_type: str, db: Session, business: models.Business, trigger_data: dict, config: dict) -> ActionOutcome:
    executor = ACTION_EXECUTORS.get(action_type)
    if executor is None:
        return ActionOutcome(status="failed", error=f"Unregistered action type: {action_type!r}")
    try:
        return executor(db, business, trigger_data, config)
    except Exception as exc:
        logger.exception("workflow.action_executor_error", extra={"ctx": {
            "event": "workflow.action_executor_error", "action_type": action_type, "business_id": business.id,
        }})
        return ActionOutcome(status="failed", error=f"Unexpected error running {action_type}: {exc}")
