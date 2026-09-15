"""
Phase 10C: the minimal approval inbox for AIActionApproval (Phase 10A's
generic AI-action approval primitive) - agency/tenant-scoped via
get_current_agency, matching every other dashboard router
(app/routers/workflows.py's workflow-approvals endpoints are the exact
pattern this mirrors). Approving here also EXECUTES the action, for
action_types that have a registered handler
(app.services.ai_workforce.action_execution) - see
AIActionApprovalService.approve_and_execute()'s own docstring for why
that is still never "approval alone magically executing arbitrary
payload data".
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency, get_current_user
from app.services.ai_workforce.approval_service import (
    AIActionApprovalService, ApprovalNotFoundError, InvalidApprovalTransitionError,
)

router = APIRouter(prefix="/ai-approvals", tags=["AI Action Approvals"])


@router.get("", response_model=list[schemas.AIActionApprovalOut])
def list_ai_approvals(
    pending_only: bool = True,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    svc = AIActionApprovalService(db)
    if pending_only:
        return svc.list_pending(agency.id)
    return (
        db.query(models.AIActionApproval)
        .filter(models.AIActionApproval.agency_id == agency.id)
        .order_by(models.AIActionApproval.created_at.desc())
        .all()
    )


@router.post("/{approval_id}/decide", response_model=schemas.AIActionApprovalOut)
def decide_ai_approval(
    approval_id: str,
    payload: schemas.ApprovalDecisionRequest,
    agency: models.Agency = Depends(get_current_agency),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = AIActionApprovalService(db)
    try:
        if payload.approve:
            row, _execution_result = svc.approve_and_execute(approval_id, agency, decided_by_user_id=user.id)
        else:
            row = svc.reject(approval_id, agency.id, decided_by_user_id=user.id)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail="Approval not found")
    except InvalidApprovalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return row
