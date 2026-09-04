from sqlalchemy.orm import Session

from app.services.llm_client import chat_completion


class CampaignTool:
    """Drafts marketing copy (captions, posts, promo ideas) grounded in the
    business's own configured profile.

    The project has no campaign-management/persistence model yet, so this
    tool produces ready-to-post copy rather than storing a campaign record -
    it never invents offers or facts the business hasn't provided."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str, db=None, business=None, conversation=None, lead=None, **kwargs) -> dict:
        if business is None:
            return {"ok": False, "error": "missing_business"}

        config = getattr(business, "chatbot_config", None)
        description = (config.business_description if config else "") or ""
        services = config.services if config and config.services else []

        prompt = f"""You are writing marketing copy for {business.name}.
Business description: {description or "Not provided."}
Services: {", ".join(services) if services else "Not provided."}

Request:
{message}

Write engaging, on-brand marketing copy (e.g. an Instagram caption or a short
promo post) based only on the facts above - never invent offers, discounts,
or facts about the business that weren't given to you."""

        draft = ""
        for attempt in range(2):
            try:
                completion = chat_completion([{"role": "user", "content": prompt}])
                draft = (completion.content or "").strip()
                break
            except Exception as exc:
                print(f"[campaign-tool:error attempt={attempt}] {exc}")

        return {"ok": bool(draft), "draft": draft or "I couldn't draft that content right now - please try again."}
