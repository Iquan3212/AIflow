from sqlalchemy.orm import Session

from app.models import (
    Business,
    ChatbotConfig,
)


def get_business_by_slug(
    db: Session,
    slug: str,
):
    """
    Find a business using its unique slug.
    """

    return (
        db.query(Business)
        .filter(Business.slug == slug)
        .first()
    )


def get_chatbot_config(
    db: Session,
    business_id: str,
):
    """
    Return the chatbot configuration for a business.
    """

    return (
        db.query(ChatbotConfig)
        .filter(ChatbotConfig.business_id == business_id)
        .first()
    )


def create_chatbot_config(
    db: Session,
    business_id: str,
):
    """
    Create the default chatbot configuration
    for a newly registered business.
    """

    config = ChatbotConfig(
        business_id=business_id,
    )

    db.add(config)
    db.commit()
    db.refresh(config)

    return config


def update_chatbot_config(
    db: Session,
    config: ChatbotConfig,
    data: dict,
):
    """
    Update only the supplied fields.
    """

    for key, value in data.items():

        setattr(config, key, value)

    db.commit()
    db.refresh(config)

    return config