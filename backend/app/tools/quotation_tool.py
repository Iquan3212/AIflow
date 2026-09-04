from sqlalchemy.orm import Session

from app.services.draft_service import DraftService
from app.services.llm_client import chat_completion


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

        prompt = f"""You are drafting a quotation summary for {business.name}.
Only reference the services listed below - never invent prices, discounts, or services.

Available services:
{chr(10).join(f"- {s}" for s in services) if services else "No services configured for this business yet."}

Customer request:
{message}

Write a short, professional quotation-style reply. If the request needs a
service that isn't listed, say plainly that it isn't offered instead of
guessing a price or availability."""

        draft = ""
        for attempt in range(2):
            try:
                completion = chat_completion([{"role": "user", "content": prompt}])
                draft = (completion.content or "").strip()
                break
            except Exception as exc:
                print(f"[quotation-tool:error attempt={attempt}] {exc}")

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
