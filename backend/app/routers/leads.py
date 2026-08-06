from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_business
from app.models import Business
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
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.get_all(business.id)


@router.post(
    "/",
    response_model=schemas.LeadOut,
)
def create_new_lead(
    payload: schemas.LeadCreate,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    service = LeadService(db)

    return service.create(
        business.id,
        payload,
    )


@router.put(
    "/{lead_id}",
    response_model=schemas.LeadOut,
)
def update_existing_lead(
    lead_id: UUID,
    payload: schemas.LeadUpdate,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    service = LeadService(db)

    lead = service.update(
        lead_id,
        business.id,
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
    lead_id: UUID,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    service = LeadService(db)

    success = service.delete(
        lead_id,
        business.id,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Lead not found",
        )

    return {
        "message": "Lead deleted successfully"
    }