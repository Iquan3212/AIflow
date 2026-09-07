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


class QuotationTool:
    """Drafts a quotation grounded in the business's configured services.

    The project has no dedicated pricing/quotation model yet, so this tool
    never invents numbers - it composes a quote-style reply using only the
    service list configured for the business (and the customer's stated
    budget/service, if any), matching the Finance employee's own rule of
    never inventing prices."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str, db=None, business=None, conversation=None, lead=None, **kwargs) -> dict:
        db = db or self.db
        if business is None:
            return {"ok": False, "error": "missing_business"}

        config = getattr(business, "chatbot_config", None)
        services = config.services if config and config.services else []
        services_text = "\n".join(f"- {s}" for s in services) if services else "No services configured for this business yet."

        system_prompt = harden_system_prompt(f"""You are drafting a quotation summary for {business.name}.
Only reference the services listed in the fenced data below - never invent
prices, discounts, or services that aren't there.

{wrap_untrusted("AVAILABLE SERVICES", services_text)}

Write a short, professional quotation-style reply grounded only in the data
above. If the customer's request needs a service that isn't listed, say
plainly that it isn't offered instead of guessing a price or availability.""")

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
                logger.warning("llm.retry", extra={"ctx": {"event": "llm.retry", "tool": "quotation", "attempt": attempt}}, exc_info=True)

        if draft and leaks_system_prompt(draft, system_prompt):
            logger.warning("prompt_guard.leak_detected", extra={"ctx": {"event": "prompt_guard.leak_detected", "tool": "quotation"}})
            draft = SAFE_FALLBACK_REPLY

        draft_id = None
        if draft:
            saved = DraftService(db).create(
                business_id=business.id,
                kind="quotation",
                content=draft,
                title=message[:80],
                lead_id=getattr(lead, "id", None),
            )
            draft_id = saved.id

        return {
            "ok": bool(draft),
            "services_considered": services,
            "draft": draft or "I couldn't draft a quotation right now - please try again.",
            "draft_id": draft_id,
        }
