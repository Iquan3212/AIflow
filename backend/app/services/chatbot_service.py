from sqlalchemy.orm import Session

from app.repositories.chatbot_repository import (
    get_business_by_slug,
    get_chatbot_config,
    create_chatbot_config,
    update_chatbot_config,
)

from app.services.ai_service import ask_ai


# ==========================================
# AI Reply
# ==========================================

def get_reply(
    db: Session,
    business,
    conversation,
    message: str,
):
    """
    Generates an AI response using the chatbot configuration.
    """

    config = business.chatbot_config

    if config is None:
        config = create_chatbot_config(
            db,
            business.id,
        )

    prompt = f"""
You are the AI assistant for {business.name}.

Business Description:
{config.business_description}

Services:
{config.services}

FAQs:
{config.faqs}

Tone:
{config.persona_tone}

Welcome Message:
{config.welcome_message}

Lead Questions:
{config.lead_questions}

Customer Message:
{message}

Respond naturally as an employee of the business.
"""

    return ask_ai(prompt)


# ==========================================
# Get Config
# ==========================================

def get_config(
    db: Session,
    business_slug: str,
):

    business = get_business_by_slug(
        db,
        business_slug,
    )

    if business is None:
        raise Exception("Business not found")

    config = get_chatbot_config(
        db,
        business.id,
    )

    if config is None:

        config = create_chatbot_config(
            db,
            business.id,
        )

    return {
        "welcome_message": config.welcome_message,
        "persona_tone": config.persona_tone,
        "business_description": config.business_description,
        "services": config.services,
        "faqs": config.faqs,
        "lead_questions": config.lead_questions,
    }


# ==========================================
# Save Config
# ==========================================

def save_config(
    db: Session,
    business_slug: str,
    data: dict,
):

    business = get_business_by_slug(
        db,
        business_slug,
    )

    if business is None:
        raise Exception("Business not found")

    config = get_chatbot_config(
        db,
        business.id,
    )

    if config is None:

        config = create_chatbot_config(
            db,
            business.id,
        )

    config = update_chatbot_config(
        db=db,
        config=config,
        data=data,
    )

    return {
        "message": "Configuration updated successfully.",
        "config": {
            "welcome_message": config.welcome_message,
            "persona_tone": config.persona_tone,
            "business_description": config.business_description,
            "services": config.services,
            "faqs": config.faqs,
            "lead_questions": config.lead_questions,
        },
    }