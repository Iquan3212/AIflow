from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_business

router = APIRouter(prefix="/businesses", tags=["businesses"])


# =====================================================
# BUSINESS INFO
# =====================================================

@router.get("/me", response_model=schemas.BusinessOut)
def get_my_business(
    business: models.Business = Depends(get_current_business),
):
    return business


@router.patch("/me", response_model=schemas.BusinessOut)
def update_my_business(
    payload: schemas.BusinessUpdate,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(business, field, value)
    db.commit()
    db.refresh(business)
    return business


# =====================================================
# CHATBOT CONFIG
# =====================================================

@router.get("/me/chatbot-config", response_model=schemas.ChatbotConfigOut)
def get_my_config(
    business: models.Business = Depends(get_current_business),
):
    return business.chatbot_config


@router.put("/me/chatbot-config", response_model=schemas.ChatbotConfigOut)
def update_my_config(
    payload: schemas.ChatbotConfigUpdate,
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    config = business.chatbot_config

    # Only update the fields the client actually sent.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)

    return config