"""
Gmail as a Tool Router capability. Four separate tools (one execute() per
action, matching every other tool in this app - one fixed entrypoint per
tool_name, permission-checked by ToolRouter/Registry exactly like
LeadTool/AppointmentTool/QuotationTool) rather than one tool with an
internal action switch, since ToolRouter dispatches by tool_name alone.

Each tool prefers explicit structured kwargs (to/subject/body/query/
message_id) when a caller already has them - passing those makes the tool
fully deterministic and testable with zero LLM calls. Only when they're
missing does it fall back to app.services.gmail.gmail_ai_service's LLM
extraction from the free-text `message`, mirroring exactly how LeadTool
falls back to lead_ai_service.extract_lead_information().

None of these ever fabricate success: GmailService already returns
ok=False with a real reason (not_connected/read_only_mode/not_available/
provider_error) whenever the real Gmail API wasn't actually reached, and
send() under approval_required mode returns sent=False + a real
pending_action_id rather than pretending the email went out.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services.gmail import gmail_ai_service
from app.services.gmail.gmail_service import GmailService


class GmailStatusTool:
    """Deterministic connection/capability check - no real Gmail API call,
    no LLM extraction (unlike the other four tools here). Lets Manager
    answer a capability question ("do you have access to my Gmail?") from
    real, current application state (GmailCredential row - connected,
    scopes/send_mode) instead of the model guessing or inventing an
    answer, and instead of running a semantically-wrong real search just
    to find out whether it's even connected."""

    def execute(
        self, message: str, db: Session = None, business: models.Business = None,
        conversation=None, lead=None, **kwargs,
    ) -> dict:
        if business is None:
            return {"ok": False, "error": "missing_business"}
        return GmailService(db).status(business)


class GmailSearchTool:
    def execute(
        self, message: str, db: Session = None, business: models.Business = None,
        conversation=None, lead=None, query: str | None = None, max_results: int = 10, **kwargs,
    ) -> dict:
        if business is None:
            return {"ok": False, "error": "missing_business"}
        if query is None:
            query = gmail_ai_service.extract_search_request(message).get("query") or message
        return GmailService(db).search(business, query, max_results=max_results)


class GmailReadTool:
    def execute(
        self, message: str, db: Session = None, business: models.Business = None,
        conversation=None, lead=None, message_id: str | None = None, **kwargs,
    ) -> dict:
        if business is None:
            return {"ok": False, "error": "missing_business"}
        if not message_id:
            return {"ok": False, "error": "missing_message_id", "message": "A Gmail message id is required to read a specific email."}
        return GmailService(db).read(business, message_id)


class GmailDraftTool:
    def execute(
        self, message: str, db: Session = None, business: models.Business = None,
        conversation=None, lead=None, employee: str | None = None,
        to: str | None = None, subject: str | None = None, body: str | None = None, **kwargs,
    ) -> dict:
        if business is None:
            return {"ok": False, "error": "missing_business"}
        if not (to and body):
            extracted = gmail_ai_service.extract_send_request(message)
            to = to or extracted.get("to")
            subject = subject or extracted.get("subject")
            body = body or extracted.get("body")
        if not to or not body:
            return {"ok": False, "error": "missing_fields", "message": "A recipient and a body are required to draft an email."}
        return GmailService(db).draft(business, to=to, subject=subject or "", body=body, employee=employee)


class GmailSendTool:
    def execute(
        self, message: str, db: Session = None, business: models.Business = None,
        conversation=None, lead=None, employee: str | None = None,
        to: str | None = None, subject: str | None = None, body: str | None = None, **kwargs,
    ) -> dict:
        if business is None:
            return {"ok": False, "error": "missing_business"}
        if not (to and body):
            extracted = gmail_ai_service.extract_send_request(message)
            to = to or extracted.get("to")
            subject = subject or extracted.get("subject")
            body = body or extracted.get("body")
        if not to or not body:
            return {"ok": False, "error": "missing_fields", "message": "A recipient and a body are required to send an email."}
        conversation_id = getattr(conversation, "id", None)
        return GmailService(db).send(
            business, to=to, subject=subject or "", body=body, employee=employee, conversation_id=conversation_id,
        )
