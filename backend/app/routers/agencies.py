from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency

router = APIRouter(prefix="/agencies", tags=["agencies"])


# =====================================================
# BUSINESS INFO
# =====================================================

@router.get("/me", response_model=schemas.AgencyOut)
def get_my_agency(
    agency: models.Agency = Depends(get_current_agency),
):
    return agency


@router.patch("/me", response_model=schemas.AgencyOut)
def update_my_agency(
    payload: schemas.AgencyUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agency, field, value)
    db.commit()
    db.refresh(agency)
    return agency


# =====================================================
# CHATBOT CONFIG
# =====================================================

@router.get("/me/chatbot-config", response_model=schemas.ChatbotConfigOut)
def get_my_config(
    agency: models.Agency = Depends(get_current_agency),
):
    return agency.chatbot_config


@router.put("/me/chatbot-config", response_model=schemas.ChatbotConfigOut)
def update_my_config(
    payload: schemas.ChatbotConfigUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    config = agency.chatbot_config

    # Only update the fields the client actually sent.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)

    return config