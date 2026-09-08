"""
Controlled Workflow Automation API (Phase 5) - all authenticated, all
business/tenant-scoped via get_current_business, matching every other
CRUD router in this app (drafts.py, knowledge.py, gmail.py). This is the
ONLY way a Workflow can ever be created or changed - see
services/workflows/service.py's validate_workflow_config() for why an
invalid trigger/condition/action is rejected here, before it can ever be
saved.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_business, get_current_user
from app.services.workflows.engine import WorkflowEngine
from app.services.workflows.service import WorkflowService, WorkflowValidationError

router = APIRouter(tags=["Workflows"])


def _to_trigger_type(value: str) -> models.WorkflowTriggerType:
    try:
        return models.WorkflowTriggerType(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown trigger_type: {value!r}")


@router.get("/workflows", response_model=list[schemas.WorkflowOut])
def list_workflows(
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return WorkflowService(db).get_all(business.id)


@router.post("/workflows", response_model=schemas.WorkflowOut, status_code=201)
def create_workflow(
    payload: schemas.WorkflowCreate,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    try:
        return WorkflowService(db).create(
            business_id=business.id, name=payload.name, description=payload.description,
            trigger_type=_to_trigger_type(payload.trigger_type),
            conditions=[c.model_dump() for c in payload.conditions],
            actions=[a.model_dump() for a in payload.actions],
        )
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/workflows/{workflow_id}", response_model=schemas.WorkflowOut)
def get_workflow(
    workflow_id: str,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    workflow = WorkflowService(db).get(workflow_id, business.id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.put("/workflows/{workflow_id}", response_model=schemas.WorkflowOut)
def update_workflow(
    workflow_id: str,
    payload: schemas.WorkflowUpdate,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    try:
        workflow = WorkflowService(db).update(
            workflow_id, business.id,
            name=payload.name, description=payload.description,
            conditions=[c.model_dump() for c in payload.conditions] if payload.conditions is not None else None,
            actions=[a.model_dump() for a in payload.actions] if payload.actions is not None else None,
        )
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.delete("/workflows/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    if not WorkflowService(db).delete(workflow_id, business.id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"message": "Workflow deleted successfully"}


@router.post("/workflows/{workflow_id}/enable", response_model=schemas.WorkflowOut)
def enable_workflow(
    workflow_id: str,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    workflow = WorkflowService(db).set_status(workflow_id, business.id, models.WorkflowStatus.active)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("/workflows/{workflow_id}/disable", response_model=schemas.WorkflowOut)
def disable_workflow(
    workflow_id: str,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    workflow = WorkflowService(db).set_status(workflow_id, business.id, models.WorkflowStatus.disabled)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get("/workflows/{workflow_id}/runs", response_model=list[schemas.WorkflowRunOut])
def list_workflow_runs(
    workflow_id: str,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return WorkflowService(db).get_runs(workflow_id, business.id)


@router.get("/workflow-runs/{run_id}", response_model=schemas.WorkflowRunOut)
def get_workflow_run(
    run_id: str,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    run = WorkflowService(db).get_run(run_id, business.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


@router.get("/workflow-approvals", response_model=list[schemas.ApprovalRequestOut])
def list_workflow_approvals(
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.ApprovalRequest)
        .filter(models.ApprovalRequest.business_id == business.id)
        .order_by(models.ApprovalRequest.created_at.desc())
        .all()
    )


@router.post("/workflow-approvals/{approval_id}/decide", response_model=schemas.ApprovalRequestOut)
def decide_workflow_approval(
    approval_id: str,
    payload: schemas.ApprovalDecisionRequest,
    business: models.Business = Depends(get_current_business),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    approval = (
        db.query(models.ApprovalRequest)
        .filter(models.ApprovalRequest.id == approval_id, models.ApprovalRequest.business_id == business.id)
        .first()
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")

    # Atomic conditional UPDATE (not read-then-write): only a request that
    # actually flips a row still in "pending" wins. Two simultaneous
    # decide calls on the same approval can both pass the plain SELECT
    # above before either commits - Postgres serializes the UPDATEs
    # themselves, so exactly one affects a row and the other sees 0,
    # closing the same double-decide race GmailPendingAction already
    # guards against (see test_cannot_decide_twice in test_gmail_service.py).
    new_status = models.ApprovalRequestStatus.approved if payload.approve else models.ApprovalRequestStatus.rejected
    updated = (
        db.query(models.ApprovalRequest)
        .filter(
            models.ApprovalRequest.id == approval_id,
            models.ApprovalRequest.status == models.ApprovalRequestStatus.pending,
        )
        .update({
            "status": new_status,
            "decided_at": datetime.utcnow(),
            "decided_by_user_id": user.id,
        }, synchronize_session=False)
    )
    db.commit()
    if updated == 0:
        db.refresh(approval)
        raise HTTPException(status_code=409, detail=f"Already decided (status={approval.status.value})")
    db.refresh(approval)

    WorkflowEngine(db).resume_after_approval(approval, decided_by_user_id=user.id)
    db.refresh(approval)
    return approval
