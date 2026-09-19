"""
Agency-side view/management of buyer callback requests.

  GET   /callbacks                 list this agency's callback requests
  GET   /callbacks/{id}            one callback request
  POST  /callbacks/{id}/assign     assign to a team member (defaults to self)
  POST  /callbacks/{id}/contacted  mark that staff has reached the buyer
  POST  /callbacks/{id}/complete   mark the callback done
  POST  /callbacks/{id}/cancel     cancel the request

Any signed-in team member (owner/admin/member) may view and act on
callbacks - the same authorization level every other CRM object (leads,
appointments) already uses; see deps.get_current_agency. AIFlow never
places the call itself - see app/services/callback_service.py's module
docstring for the full model.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency, get_current_user
from app.services import callback_service

router = APIRouter(prefix="/callbacks", tags=["Callbacks"])


@router.get("", response_model=list[schemas.CallbackRequestOut])
def list_callbacks(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return callback_service.list_for_agency(db, agency.id)


@router.get("/{callback_id}", response_model=schemas.CallbackRequestOut)
def get_callback(
    callback_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    callback = callback_service.get(db, agency.id, callback_id)
    if callback is None:
        raise HTTPException(status_code=404, detail="Callback request not found.")
    return callback


@router.post("/{callback_id}/assign", response_model=schemas.CallbackRequestOut)
def assign_callback(
    callback_id: str,
    payload: schemas.CallbackAssignRequest,
    agency: models.Agency = Depends(get_current_agency),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignee_id = str(payload.assigned_to_user_id) if payload.assigned_to_user_id else user.id
    assignee = (
        db.query(models.User)
        .filter(models.User.id == assignee_id, models.User.agency_id == agency.id)
        .first()
    )
    if assignee is None:
        raise HTTPException(status_code=422, detail="That user is not a member of this agency.")
    try:
        return callback_service.assign(db, agency.id, callback_id, assigned_to_user_id=assignee.id)
    except callback_service.CallbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except callback_service.InvalidCallbackTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{callback_id}/contacted", response_model=schemas.CallbackRequestOut)
def mark_callback_contacted(
    callback_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        return callback_service.mark_contacted(db, agency.id, callback_id)
    except callback_service.CallbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except callback_service.InvalidCallbackTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{callback_id}/complete", response_model=schemas.CallbackRequestOut)
def complete_callback(
    callback_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        return callback_service.complete(db, agency.id, callback_id)
    except callback_service.CallbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except callback_service.InvalidCallbackTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{callback_id}/cancel", response_model=schemas.CallbackRequestOut)
def cancel_callback(
    callback_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        return callback_service.cancel(db, agency.id, callback_id)
    except callback_service.CallbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except callback_service.InvalidCallbackTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
