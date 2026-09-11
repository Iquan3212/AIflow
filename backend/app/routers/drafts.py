from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_agency
from app.models import Agency
from app.services.draft_service import DraftService

router = APIRouter(prefix="/drafts", tags=["Drafts"])


@router.get("/", response_model=list[schemas.AIDraftOut])
def list_drafts(
    kind: str | None = Query(default=None, pattern="^(quotation|campaign)$"),
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return DraftService(db).get_all(agency.id, kind=kind)


@router.get("/{draft_id}", response_model=schemas.AIDraftOut)
def get_draft(
    draft_id: str,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    draft = DraftService(db).get(draft_id, agency.id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.patch("/{draft_id}", response_model=schemas.AIDraftOut)
def update_draft(
    draft_id: str,
    payload: schemas.AIDraftUpdate,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    draft = DraftService(db).update_status(draft_id, agency.id, payload.status)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.delete("/{draft_id}")
def delete_draft(
    draft_id: str,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    success = DraftService(db).delete(draft_id, agency.id)
    if not success:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"message": "Draft deleted successfully"}
