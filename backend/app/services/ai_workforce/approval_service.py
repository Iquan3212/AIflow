"""
Phase 10A: the AIActionApproval primitive - a generic, action-type-agnostic
"a human must decide" gate for AI-workforce tools. Deliberately separate
from app.services.workflows' ApprovalRequest (only creatable inside a
Workflow step-run - see app/models.py's ApprovalRequestStatus/
ApprovalRequest) and from GmailPendingAction (Gmail-send-specific).

approve()/reject() only ever manage the decision record - they never
execute anything (Phase 10A's Step 6: "must NOT automatically perform
an action merely because a record is approved" - still true of these
two methods).

Phase 10C: approve_and_execute()/reject_and_record() are the explicit,
opt-in path a caller (e.g. the /ai-approvals router) uses when it wants
approving to ALSO run the real action - never implicit, never triggered
by status alone. Execution is routed through
app.services.ai_workforce.action_execution's fixed action_type ->
handler registry (never eval()/arbitrary dispatch of the stored
payload), and only for an action_type that actually has a registered
handler - every other action_type stays exactly as decision-only as it
already was in 10A/10B.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app import models
from app.services.ai_workforce import action_execution


class ApprovalNotFoundError(ValueError):
    pass


class InvalidApprovalTransitionError(ValueError):
    def __init__(self, current: models.AIActionApprovalStatus):
        self.current = current
        super().__init__(f"Cannot decide an approval that is already '{current.value}'.")


class AIActionApprovalService:
    def __init__(self, db: Session):
        self.db = db

    def request(
        self,
        agency_id: UUID,
        *,
        action_type: str,
        summary: str,
        payload: dict,
        requested_by_employee: str,
    ) -> models.AIActionApproval:
        row = models.AIActionApproval(
            agency_id=agency_id,
            action_type=action_type,
            summary=summary,
            payload=payload or {},
            requested_by_employee=requested_by_employee,
            status=models.AIActionApprovalStatus.pending,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get(self, approval_id: UUID, agency_id: UUID) -> models.AIActionApproval | None:
        return (
            self.db.query(models.AIActionApproval)
            .filter(
                models.AIActionApproval.id == approval_id,
                models.AIActionApproval.agency_id == agency_id,
            )
            .first()
        )

    def list_pending(self, agency_id: UUID) -> list[models.AIActionApproval]:
        return (
            self.db.query(models.AIActionApproval)
            .filter(
                models.AIActionApproval.agency_id == agency_id,
                models.AIActionApproval.status == models.AIActionApprovalStatus.pending,
            )
            .order_by(models.AIActionApproval.created_at.asc())
            .all()
        )

    def _decide(
        self, approval_id: UUID, agency_id: UUID, *, new_status: models.AIActionApprovalStatus, decided_by_user_id: UUID | None,
    ) -> models.AIActionApproval:
        row = self.get(approval_id, agency_id)
        if row is None:
            raise ApprovalNotFoundError(f"No AIActionApproval {approval_id} for agency {agency_id}")

        from datetime import datetime

        # Atomic conditional UPDATE (not read-then-write): only a call
        # that actually flips a row still "pending" wins - closes the
        # same double-decide race app/routers/workflows.py's
        # decide_workflow_approval() already guards against for
        # ApprovalRequest (two simultaneous decide calls can both pass
        # the plain SELECT above before either commits; Postgres
        # serializes the UPDATEs themselves, so exactly one affects a
        # row and the other sees 0).
        updated = (
            self.db.query(models.AIActionApproval)
            .filter(
                models.AIActionApproval.id == approval_id,
                models.AIActionApproval.status == models.AIActionApprovalStatus.pending,
            )
            .update({
                "status": new_status,
                "decided_at": datetime.utcnow(),
                "decided_by_user_id": decided_by_user_id,
            }, synchronize_session=False)
        )
        self.db.commit()
        self.db.refresh(row)
        if updated == 0:
            raise InvalidApprovalTransitionError(row.status)
        return row

    def approve(self, approval_id: UUID, agency_id: UUID, *, decided_by_user_id: UUID | None = None) -> models.AIActionApproval:
        return self._decide(approval_id, agency_id, new_status=models.AIActionApprovalStatus.approved, decided_by_user_id=decided_by_user_id)

    def reject(self, approval_id: UUID, agency_id: UUID, *, decided_by_user_id: UUID | None = None) -> models.AIActionApproval:
        return self._decide(approval_id, agency_id, new_status=models.AIActionApprovalStatus.rejected, decided_by_user_id=decided_by_user_id)

    def approve_and_execute(
        self, approval_id: UUID, agency: models.Agency, *, decided_by_user_id: UUID | None = None,
    ) -> tuple[models.AIActionApproval, dict | None]:
        """Approves (same validated pending->approved transition as
        approve() - an already-decided approval still raises
        InvalidApprovalTransitionError, a cross-agency id still raises
        ApprovalNotFoundError), then - only for an action_type with a
        registered handler - executes it through the real, authoritative
        service and persists the outcome onto `execution_result`.
        Execution re-validates against the CURRENT DB state (the handler
        calls AppointmentService/GmailService fresh, never trusting the
        payload as if it were still true) - approval never bypasses
        normal service validation. Returns (approval, execution_result);
        execution_result is None when this action_type has no handler
        (stays exactly the decision-only primitive it already was)."""
        row = self.approve(approval_id, agency.id, decided_by_user_id=decided_by_user_id)
        result = action_execution.execute_approved_action(self.db, agency, row)
        if result is not None:
            row.execution_result = result
            self.db.commit()
            self.db.refresh(row)
        return row, result
