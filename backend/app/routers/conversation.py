from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency
from app.rate_limit import limiter, CHAT_RATE_LIMIT
from app.services.shared.conversation_service import (
    process_message,
    get_agency_conversations,
)

router = APIRouter(prefix="/conversation", tags=["Conversation"])
# Compatibility routes for the shipped widget.  They keep the original
# /chat URLs working while the documented API remains /conversation/send.
compat_router = APIRouter(tags=["Conversation"])


class ChatRequest(BaseModel):
    agency_slug: str
    visitor_id: str
    conversation_id: str | None = None
    message: str


@router.get("/", response_model=list[schemas.ConversationSummaryOut])
def get_conversations(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    """Owner-only: list this agency's conversations. Requires the auth token —
    previously this was public by slug, which exposed every customer chat."""
    return get_agency_conversations(db=db, agency_slug=agency.slug)


def _send_message_impl(chat: ChatRequest, db: Session):
    return process_message(
        db=db,
        agency_slug=chat.agency_slug,
        visitor_id=chat.visitor_id,
        conversation_id=chat.conversation_id,
        message=chat.message,
    )


@router.post("/send")
@limiter.limit(CHAT_RATE_LIMIT)
def send_message(
    request: Request,
    chat: ChatRequest,
    db: Session = Depends(get_db),
):
    """Public: the website widget posts customer messages here."""
    return _send_message_impl(chat, db)


@router.get("/{agency_slug}/welcome")
def welcome_message(agency_slug: str, db: Session = Depends(get_db)):
    agency = db.query(models.Agency).filter(models.Agency.slug == agency_slug).first()
    if agency is None:
        return {"agency_name": "", "welcome_message": "Hi! How can I help you today?"}
    config = agency.chatbot_config
    return {
        "agency_name": agency.name,
        "welcome_message": config.welcome_message if config else "Hi! How can I help you today?",
    }


@compat_router.post("/chat")
@limiter.limit(CHAT_RATE_LIMIT)
def legacy_send_message(request: Request, chat: ChatRequest, db: Session = Depends(get_db)):
    return _send_message_impl(chat, db)


@compat_router.get("/chat/{agency_slug}/welcome")
def legacy_welcome_message(agency_slug: str, db: Session = Depends(get_db)):
    return welcome_message(agency_slug, db)
