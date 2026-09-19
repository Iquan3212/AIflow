from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency
from app.models import Agency
from app.services.lead_service import LeadService

router = APIRouter(
    prefix="/leads",
    tags=["Leads"],
)


def _attach_latest_callback(db: Session, agency_id, leads: list[models.Lead]) -> list[models.Lead]:
    """LeadOut's `callback_request` field has no real SQLAlchemy
    relationship behind it (a Lead can have several CallbackRequest rows
    over time; only the most recent one is shown) - so it's computed
    here and set as a plain attribute, the same way Pydantic's
    from_attributes already reads `lead.property` off the real
    relationship. Missing entirely just means "no callback" (Pydantic's
    from_attributes defaults an unset field to None - see LeadOut)."""
    lead_ids = [lead.id for lead in leads]
    if not lead_ids:
        return leads
    callbacks = (
        db.query(models.CallbackRequest)
        .filter(models.CallbackRequest.agency_id == agency_id, models.CallbackRequest.lead_id.in_(lead_ids))
        .order_by(models.CallbackRequest.requested_at.desc())
        .all()
    )
    latest_by_lead = {}
    for cb in callbacks:
        latest_by_lead.setdefault(cb.lead_id, cb)
    for lead in leads:
        lead.callback_request = latest_by_lead.get(lead.id)
    return leads


@router.get(
    "/",
    response_model=list[schemas.LeadOut],
)
def list_leads(
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    leads = service.get_all(agency.id)
    return _attach_latest_callback(db, agency.id, leads)


@router.post(
    "/",
    response_model=schemas.LeadOut,
)
def create_new_lead(
    payload: schemas.LeadCreate,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    service = LeadService(db)

    return service.create(
        agency.id,
        payload,
    )


@router.put(
    "/{lead_id}",
    response_model=schemas.LeadOut,
)
def update_existing_lead(
    lead_id: str,
    payload: schemas.LeadUpdate,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    service = LeadService(db)

    lead = service.update(
        lead_id,
        agency.id,
        payload,
    )

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    _attach_latest_callback(db, agency.id, [lead])
    return lead


@router.delete(
    "/{lead_id}",
)
def delete_existing_lead(
    lead_id: str,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    service = LeadService(db)

    success = service.delete(
        lead_id,
        agency.id,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return {
        "message": "Lead deleted successfully"
    }
