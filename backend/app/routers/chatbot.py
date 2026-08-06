from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.chatbot_service import (
    get_config,
    save_config,
)

router = APIRouter(
    prefix="/chatbot",
    tags=["Chatbot"],
)


class ChatbotConfigRequest(BaseModel):
    business_slug: str
    welcome_message: str
    persona_tone: str
    business_description: str
    services: list[str]
    faqs: list
    lead_questions: list[str]


@router.get("/config")
def chatbot_config(
    business_slug: str,
    db: Session = Depends(get_db),
):
    return get_config(
        db=db,
        business_slug=business_slug,
    )


@router.put("/config")
def update_chatbot_config(
    payload: ChatbotConfigRequest,
    db: Session = Depends(get_db),
):
    return save_config(
        db=db,
        business_slug=payload.business_slug,
        data={
            "welcome_message": payload.welcome_message,
            "persona_tone": payload.persona_tone,
            "business_description": payload.business_description,
            "services": payload.services,
            "faqs": payload.faqs,
            "lead_questions": payload.lead_questions,
        },
    )