from sqlalchemy.orm import Session

from app import models


def get_business_by_slug(db: Session, slug: str):
    return (
        db.query(models.Business)
        .filter(models.Business.slug == slug)
        .first()
    )


def get_conversation(
    db: Session,
    conversation_id: str,
    business_id: str | None = None,
    visitor_id: str | None = None,
    channel: str | None = None,
):
    """Load a conversation only when it belongs to the supplied scope."""
    query = db.query(models.Conversation).filter(models.Conversation.id == conversation_id)
    if business_id is not None:
        query = query.filter(models.Conversation.business_id == business_id)
    if visitor_id is not None:
        query = query.filter(models.Conversation.visitor_id == visitor_id)
    if channel is not None:
        query = query.filter(models.Conversation.channel == channel)
    return query.first()


def find_conversation_by_visitor(
    db: Session,
    business_id: str,
    visitor_id: str,
    channel: str,
):
    """Most recent conversation for this visitor on this channel, if any -
    used when the caller has no remembered conversation_id of its own. The
    website widget always sends back the conversation_id it stored in
    localStorage after the first message, so this only matters there on a
    visitor's very first-ever message (where it correctly finds nothing).
    A webhook channel (WhatsApp/Instagram) has no client-side memory at
    all, so every inbound message relies on this to find the customer's
    ongoing conversation instead of starting a new one each time."""
    return (
        db.query(models.Conversation)
        .filter(
            models.Conversation.business_id == business_id,
            models.Conversation.visitor_id == visitor_id,
            models.Conversation.channel == channel,
        )
        .order_by(models.Conversation.started_at.desc())
        .first()
    )


def create_conversation(
    db: Session,
    business_id: str,
    visitor_id: str,
    channel: str = "website",
):
    conversation = models.Conversation(
        business_id=business_id,
        visitor_id=visitor_id,
        channel=channel,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def save_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
):
    message = models.Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )

    db.add(message)
    db.commit()

    return message


def load_history(
    db: Session,
    conversation_id: str,
):
    history = (
        db.query(models.Message)
        .filter(
            models.Message.conversation_id == conversation_id
        )
        .order_by(models.Message.created_at)
        .all()
    )

    return history
def get_business_conversations(db: Session, business_id: str, channel: str | None = None):
    query = db.query(models.Conversation).filter(models.Conversation.business_id == business_id)
    if channel is not None:
        query = query.filter(models.Conversation.channel == channel)
    return query.order_by(models.Conversation.started_at.desc()).all()
def get_or_create_employee_conversation(
    db: Session,
    business_id: str,
    conversation_id: str | None = None,
):
    """
    Returns the dashboard AI conversation for this business.
    Creates one if it doesn't exist.
    """

    if conversation_id:
        conversation = get_conversation(
            db,
            conversation_id,
            business_id=business_id,
            channel="employee",
        )
        if conversation is not None:
            return conversation

    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.business_id == business_id,
            models.Conversation.channel == "employee",
        )
        .first()
    )

    if conversation:
        return conversation

    conversation = models.Conversation(
        business_id=business_id,
        visitor_id="dashboard-owner",
        channel="employee",
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation
