"""
Phase 10A: the AIActionApproval primitive - a generic, action-type-agnostic
"a human must decide" gate for AI-workforce tools. Deliberately separate
from app.services.workflows' ApprovalRequest (only creatable inside a
Workflow step-run - see app/models.py's ApprovalRequestStatus/
ApprovalRequest) and from GmailPendingAction (Gmail-send-specific).

This service only ever manages the decision record. Approving a row here
does NOT perform the underlying action - nothing in this codebase reads
an "approved" AIActionApproval and automatically executes it. That wiring
is explicitly out of scope for Phase 10A (see the Phase 10A spec's Step 6:
"must NOT automatically perform an action merely because a record is
approved").
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app import models


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
        if row.status != models.AIActionApprovalStatus.pending:
            raise InvalidApprovalTransitionError(row.status)

        from datetime import datetime

        row.status = new_status
        row.decided_at = datetime.utcnow()
        row.decided_by_user_id = decided_by_user_id
        self.db.commit()
        self.db.refresh(row)
        return row

    def approve(self, approval_id: UUID, agency_id: UUID, *, decided_by_user_id: UUID | None = None) -> models.AIActionApproval:
        return self._decide(approval_id, agency_id, new_status=models.AIActionApprovalStatus.approved, decided_by_user_id=decided_by_user_id)

    def reject(self, approval_id: UUID, agency_id: UUID, *, decided_by_user_id: UUID | None = None) -> models.AIActionApproval:
        return self._decide(approval_id, agency_id, new_status=models.AIActionApprovalStatus.rejected, decided_by_user_id=decided_by_user_id)
