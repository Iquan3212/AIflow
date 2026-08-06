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


def create_conversation(
    db: Session,
    business_id: str,
    visitor_id: str,
):
    conversation = models.Conversation(
        business_id=business_id,
        visitor_id=visitor_id,
        channel="website",
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
def get_business_conversations(db: Session, business_id: str):
    return (
        db.query(models.Conversation)
        .filter(models.Conversation.business_id == business_id)
        .order_by(models.Conversation.started_at.desc())
        .all()
    )
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
