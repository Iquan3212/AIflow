from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_agency
from app.models import Agency
from app.services.lead_service import LeadService

router = APIRouter(
    prefix="/leads",
    tags=["Leads"],
)


@router.get(
    "/",
    response_model=list[schemas.LeadOut],
)
def list_leads(
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.get_all(agency.id)


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
