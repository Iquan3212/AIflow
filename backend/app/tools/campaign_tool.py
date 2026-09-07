from sqlalchemy.orm import Session

from app.agents.prompt_guard import (
    harden_system_prompt,
    wrap_untrusted,
    detect_injection_signals,
    INJECTION_REINFORCEMENT,
    leaks_system_prompt,
    SAFE_FALLBACK_REPLY,
)
from app.logging_config import get_logger
from app.services.draft_service import DraftService
from app.services.llm_client import chat_completion

logger = get_logger(__name__)


class CampaignTool:
    """Drafts marketing copy (captions, posts, promo ideas) grounded in the
    business's own configured profile, and persists it as an AIDraft so it
    can be reviewed later from the Drafts page instead of only existing in
    the chat transcript.

    It never invents offers or facts the business hasn't provided."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str, db=None, business=None, conversation=None, lead=None, **kwargs) -> dict:
        db = db or self.db
        if business is None:
            return {"ok": False, "error": "missing_business"}

        config = getattr(business, "chatbot_config", None)
        description = (config.business_description if config else "") or ""
        services = config.services if config and config.services else []

        business_facts = wrap_untrusted(
            "BUSINESS FACTS",
            f"Business description: {description or 'Not provided.'}\n"
            f"Services: {', '.join(services) if services else 'Not provided.'}",
        )
        system_prompt = harden_system_prompt(f"""You are writing marketing copy for {business.name}.

{business_facts}

Write engaging, on-brand marketing copy (e.g. an Instagram caption or a short
promo post) based only on the facts above - never invent offers, discounts,
or facts about the business that weren't given to you.""")

        messages = [{"role": "system", "content": system_prompt}]
        if detect_injection_signals(message):
            messages.append({"role": "system", "content": INJECTION_REINFORCEMENT})
        messages.append({"role": "user", "content": message})

        draft = ""
        for attempt in range(2):
            try:
                completion = chat_completion(messages)
                draft = (completion.content or "").strip()
                break
            except Exception:
                logger.warning("llm.retry", extra={"ctx": {"event": "llm.retry", "tool": "campaign", "attempt": attempt}}, exc_info=True)

        if draft and leaks_system_prompt(draft, system_prompt):
            logger.warning("prompt_guard.leak_detected", extra={"ctx": {"event": "prompt_guard.leak_detected", "tool": "campaign"}})
            draft = SAFE_FALLBACK_REPLY

        draft_id = None
        if draft:
            saved = DraftService(db).create(
                business_id=business.id,
                kind="campaign",
                content=draft,
                title=message[:80],
                lead_id=getattr(lead, "id", None),
            )
            draft_id = saved.id

        return {
            "ok": bool(draft),
            "draft": draft or "I couldn't draft that content right now - please try again.",
            "draft_id": draft_id,
        }
