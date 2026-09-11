"""
Gmail agency logic: enforces send_mode (read_only / approval_required /
automated) around the raw adapter calls, and owns the GmailPendingAction
approval queue. GmailTool (app/tools/gmail_tool.py) calls this, never
GmailAdapter directly - this is where "never silently execute an
approval-required action" is actually enforced, in one place.
"""

from __future__ import annotations

from datetime import datetime

from app import models
from app.logging_config import get_logger
from app.services.gmail.gmail_adapter import GmailAdapter, GmailNotAvailableError

logger = get_logger(__name__)

READ_ONLY = "read_only"
APPROVAL_REQUIRED = "approval_required"
AUTOMATED = "automated"
SEND_MODES = (READ_ONLY, APPROVAL_REQUIRED, AUTOMATED)


class GmailService:
    def __init__(self, db):
        self.db = db
        self.adapter = GmailAdapter(db)

    # ---- capability status - DB-only, no real Gmail API call ----------------

    def status(self, agency) -> dict:
        """Deterministic, real connection/capability state - reuses the
        exact same is_configured()/send_mode() checks every other method
        here already enforces, so this can never drift from what
        search/read/draft/send actually do. Exists so a capability
        question ("do you have access to my Gmail?") can be answered from
        real application state instead of the model guessing or a wasted
        real search - see app/tools/gmail_tool.py's GmailStatusTool."""
        connected = self.adapter.is_configured(agency)
        if not connected:
            return {
                "ok": True, "connected": False, "send_mode": None,
                "capabilities": {"search": False, "read": False, "draft": False, "send": False},
            }
        mode = self.adapter.send_mode(agency)
        return {
            "ok": True,
            "connected": True,
            "send_mode": mode,
            "capabilities": {
                "search": True,
                "read": True,
                "draft": mode != READ_ONLY,
                "send": AUTOMATED if mode == AUTOMATED else (APPROVAL_REQUIRED if mode == APPROVAL_REQUIRED else False),
            },
        }

    # ---- read actions - always allowed once connected, regardless of send_mode ----

    def search(self, agency, query: str, max_results: int = 10) -> dict:
        if not self.adapter.is_configured(agency):
            return {"ok": False, "error": "not_connected", "message": "Gmail is not connected for this agency."}
        try:
            results = self.adapter.search(agency, query, max_results)
            logger.info("gmail.search", extra={"ctx": {"event": "gmail.search", "agency_id": agency.id, "result_count": len(results)}})
            return {"ok": True, "results": results}
        except GmailNotAvailableError as exc:
            return {"ok": False, "error": "not_available", "message": str(exc)}
        except Exception as exc:
            logger.exception("gmail.search_failed", extra={"ctx": {"event": "gmail.search_failed", "agency_id": agency.id}})
            return {"ok": False, "error": "provider_error", "message": str(exc)}

    def read(self, agency, message_id: str) -> dict:
        if not self.adapter.is_configured(agency):
            return {"ok": False, "error": "not_connected", "message": "Gmail is not connected for this agency."}
        try:
            message = self.adapter.read(agency, message_id)
            logger.info("gmail.read", extra={"ctx": {"event": "gmail.read", "agency_id": agency.id, "message_id": message_id}})
            return {"ok": True, "message": message}
        except GmailNotAvailableError as exc:
            return {"ok": False, "error": "not_available", "message": str(exc)}
        except Exception as exc:
            logger.exception("gmail.read_failed", extra={"ctx": {"event": "gmail.read_failed", "agency_id": agency.id, "message_id": message_id}})
            return {"ok": False, "error": "provider_error", "message": str(exc)}

    # ---- write actions - gated by send_mode ----

    def draft(self, agency, *, to: str, subject: str, body: str, employee: str | None = None) -> dict:
        if not self.adapter.is_configured(agency):
            return {"ok": False, "error": "not_connected", "message": "Gmail is not connected for this agency."}

        mode = self.adapter.send_mode(agency)
        if mode == READ_ONLY:
            return {"ok": False, "error": "read_only_mode", "message": "Gmail is connected in read-only mode; drafting is disabled."}

        # A draft sits in the connected mailbox's Drafts folder and reaches
        # nobody - safe to create immediately in both approval_required and
        # automated mode.
        try:
            result = self.adapter.create_draft(agency, to, subject, body)
            logger.info("gmail.draft_created", extra={"ctx": {
                "event": "gmail.draft_created", "agency_id": agency.id, "employee": employee,
            }})
            return {"ok": True, **result}
        except GmailNotAvailableError as exc:
            return {"ok": False, "error": "not_available", "message": str(exc)}
        except Exception as exc:
            logger.exception("gmail.draft_failed", extra={"ctx": {"event": "gmail.draft_failed", "agency_id": agency.id}})
            return {"ok": False, "error": "provider_error", "message": str(exc)}

    def send(
        self, agency, *, to: str, subject: str, body: str,
        employee: str | None = None, conversation_id: str | None = None,
    ) -> dict:
        if not self.adapter.is_configured(agency):
            return {"ok": False, "error": "not_connected", "message": "Gmail is not connected for this agency."}

        mode = self.adapter.send_mode(agency)
        if mode == READ_ONLY:
            return {"ok": False, "error": "read_only_mode", "message": "Gmail is connected in read-only mode; sending is disabled."}

        if mode == APPROVAL_REQUIRED:
            pending = models.GmailPendingAction(
                agency_id=agency.id, conversation_id=conversation_id, employee=employee,
                action_type="send_email", to_address=to, subject=subject, body=body, status="pending",
            )
            self.db.add(pending)
            self.db.commit()
            self.db.refresh(pending)
            logger.info("gmail.send_queued_for_approval", extra={"ctx": {
                "event": "gmail.send_queued_for_approval", "agency_id": agency.id,
                "pending_action_id": pending.id, "employee": employee,
            }})
            # Truthful, not a fabricated success: this explicitly did NOT
            # send anything - it queued a real approval request.
            return {"ok": True, "queued_for_approval": True, "pending_action_id": pending.id, "sent": False}

        # automated mode - send for real immediately.
        try:
            result = self.adapter.send(agency, to, subject, body)
            logger.info("gmail.sent", extra={"ctx": {
                "event": "gmail.sent", "agency_id": agency.id, "employee": employee,
            }})
            return {"ok": True, "sent": True, **result}
        except GmailNotAvailableError as exc:
            return {"ok": False, "error": "not_available", "message": str(exc)}
        except Exception as exc:
            logger.exception("gmail.send_failed", extra={"ctx": {"event": "gmail.send_failed", "agency_id": agency.id}})
            return {"ok": False, "error": "provider_error", "message": str(exc)}

    # ---- approval queue ----

    def list_pending(self, agency, status: str | None = None) -> list["models.GmailPendingAction"]:
        q = self.db.query(models.GmailPendingAction).filter(models.GmailPendingAction.agency_id == agency.id)
        if status:
            q = q.filter(models.GmailPendingAction.status == status)
        return q.order_by(models.GmailPendingAction.created_at.desc()).all()

    def _get_pending(self, agency, pending_id: str) -> "models.GmailPendingAction | None":
        return (
            self.db.query(models.GmailPendingAction)
            .filter(models.GmailPendingAction.id == pending_id, models.GmailPendingAction.agency_id == agency.id)
            .first()
        )

    def approve(self, agency, pending_id: str, decided_by_user_id: str | None) -> dict:
        row = self._get_pending(agency, pending_id)
        if row is None:
            return {"ok": False, "error": "not_found"}
        if row.status != "pending":
            return {"ok": False, "error": "already_decided", "status": row.status}

        row.decided_at = datetime.utcnow()
        row.decided_by_user_id = decided_by_user_id

        try:
            result = self.adapter.send(agency, row.to_address, row.subject, row.body)
            row.status = "sent"
            row.gmail_message_id = result.get("message_id")
            self.db.commit()
            logger.info("gmail.pending_action_approved_and_sent", extra={"ctx": {
                "event": "gmail.pending_action_approved_and_sent", "agency_id": agency.id, "pending_action_id": row.id,
            }})
            self._resume_linked_workflow_step(row.id)
            return {"ok": True, "status": row.status, "gmail_message_id": row.gmail_message_id}
        except Exception as exc:
            row.status = "failed"
            row.error = str(exc)
            self.db.commit()
            logger.exception("gmail.pending_action_send_failed", extra={"ctx": {
                "event": "gmail.pending_action_send_failed", "agency_id": agency.id, "pending_action_id": row.id,
            }})
            self._resume_linked_workflow_step(row.id)
            return {"ok": False, "error": "send_failed", "message": str(exc)}

    def reject(self, agency, pending_id: str, decided_by_user_id: str | None) -> dict:
        row = self._get_pending(agency, pending_id)
        if row is None:
            return {"ok": False, "error": "not_found"}
        if row.status != "pending":
            return {"ok": False, "error": "already_decided", "status": row.status}

        row.status = "rejected"
        row.decided_at = datetime.utcnow()
        row.decided_by_user_id = decided_by_user_id
        self.db.commit()
        logger.info("gmail.pending_action_rejected", extra={"ctx": {
            "event": "gmail.pending_action_rejected", "agency_id": agency.id, "pending_action_id": row.id,
        }})
        self._resume_linked_workflow_step(row.id)
        return {"ok": True, "status": row.status}

    def _resume_linked_workflow_step(self, pending_action_id: str) -> None:
        """Phase 5 integration hook: a `send_gmail` workflow action that
        got queued for approval links its WorkflowStepRun to this exact
        GmailPendingAction (see services/workflows/actions.py). This is
        Gmail's OWN existing approval flow, completely unchanged above -
        this only reconciles the workflow's step/run state afterward and
        continues the chain if there is one, never re-deciding or
        re-sending anything itself. Local import to avoid a circular
        import (workflows.engine -> workflows.actions -> this module)."""
        from app.services.workflows.engine import WorkflowEngine

        step = (
            self.db.query(models.WorkflowStepRun)
            .filter(models.WorkflowStepRun.gmail_pending_action_id == pending_action_id)
            .first()
        )
        if step is None:
            return
        try:
            WorkflowEngine(self.db).resume_after_gmail_decision(step)
        except Exception:
            logger.exception("workflow.resume_after_gmail_decision_failed", extra={"ctx": {
                "event": "workflow.resume_after_gmail_decision_failed", "step_id": step.id,
            }})
