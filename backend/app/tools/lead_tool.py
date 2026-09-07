from sqlalchemy.orm import Session

from app import models
from app.services.lead_ai_service import extract_lead_information
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.notifications import preferences as notif_prefs
from app.logging_config import get_logger

logger = get_logger(__name__)


class LeadTool:
    """Persists a CRM lead extracted from natural-language text. Called by
    the Sales employee via ToolRouter, so its signature matches ToolRouter's
    calling convention: execute(message, db, business, conversation, lead, **kwargs).
    """

    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        message: str,
        db: Session = None,
        business: models.Business = None,
        conversation=None,
        lead: models.Lead = None,
        **kwargs,
    ) -> dict:
        db = db or self.db
        if business is None:
            return {"ok": False, "error": "missing_business"}

        info = extract_lead_information(message)
        name = info.get("name")
        phone = info.get("phone")
        email = info.get("email")
        service = info.get("service_interested")
        budget = info.get("budget")

        if not any([name, phone, email, service, budget]):
            return {"ok": False, "error": "no_lead_details", "buying_intent": bool(info.get("buying_intent"))}

        target = lead
        if target is None:
            query = db.query(models.Lead).filter(models.Lead.business_id == business.id)
            if phone:
                target = query.filter(models.Lead.phone == phone).first()
            if target is None and email:
                target = query.filter(models.Lead.email == email).first()
            if target is None and name:
                target = query.filter(models.Lead.name == name).first()

        created = False
        if target is None:
            target = models.Lead(business_id=business.id, status="new")
            db.add(target)
            created = True

        if name:
            target.name = name
        if phone:
            target.phone = phone
        if email:
            target.email = email
        if service:
            target.service_interested = service
        if budget:
            target.budget = budget

        db.commit()
        db.refresh(target)

        if created:
            # Best-effort: a notification failure must never undo or mask a
            # real, already-committed lead.
            try:
                NotificationDispatcher().notify_owner(
                    db=db, business=business, event_type=notif_prefs.NEW_LEAD,
                    subject=f"New lead — {business.name}",
                    body=(
                        f"A new lead came in: {target.name or 'unnamed'}"
                        f" ({target.phone or target.email or 'no contact info'})."
                        f" Interested in: {target.service_interested or 'not specified'}."
                    ),
                )
            except Exception:
                logger.exception("notification.new_lead_failed", extra={"ctx": {
                    "event": "notification.new_lead_failed", "business_id": business.id, "lead_id": target.id,
                }})

        return {
            "ok": True,
            "created": created,
            "lead_id": target.id,
            "name": target.name,
            "phone": target.phone,
            "email": target.email,
            "service_interested": target.service_interested,
            "budget": target.budget,
            "buying_intent": bool(info.get("buying_intent")),
        }
