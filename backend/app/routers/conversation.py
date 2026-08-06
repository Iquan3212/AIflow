from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.deps import get_current_business
from app.services.shared.conversation_service import (
    process_message,
    get_business_conversations,
)

router = APIRouter(prefix="/conversation", tags=["Conversation"])
# Compatibility routes for the shipped widget.  They keep the original
# /chat URLs working while the documented API remains /conversation/send.
compat_router = APIRouter(tags=["Conversation"])


class ChatRequest(BaseModel):
    business_slug: str
    visitor_id: str
    conversation_id: str | None = None
    message: str


@router.get("/")
def get_conversations(
    business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    """Owner-only: list this business's conversations. Requires the auth token —
    previously this was public by slug, which exposed every customer chat."""
    return get_business_conversations(db=db, business_slug=business.slug)


@router.post("/send")
def send_message(
    chat: ChatRequest,
    db: Session = Depends(get_db),
):
    """Public: the website widget posts customer messages here."""
    return process_message(
        db=db,
        business_slug=chat.business_slug,
        visitor_id=chat.visitor_id,
        conversation_id=chat.conversation_id,
        message=chat.message,
    )


@router.get("/{business_slug}/welcome")
def welcome_message(business_slug: str, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.slug == business_slug).first()
    if business is None:
        return {"business_name": "", "welcome_message": "Hi! How can I help you today?"}
    config = business.chatbot_config
    return {
        "business_name": business.name,
        "welcome_message": config.welcome_message if config else "Hi! How can I help you today?",
    }


@compat_router.post("/chat")
def legacy_send_message(chat: ChatRequest, db: Session = Depends(get_db)):
    return send_message(chat, db)


@compat_router.get("/chat/{business_slug}/welcome")
def legacy_welcome_message(business_slug: str, db: Session = Depends(get_db)):
    return welcome_message(business_slug, db)
