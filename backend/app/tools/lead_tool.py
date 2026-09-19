from sqlalchemy.orm import Session

from app import models, schemas
from app.services.lead_ai_service import extract_lead_information
from app.services.lead_service import LeadService
from app.services.notifications import preferences as notif_prefs
from app.services.workflows.triggers import fire_trigger, lead_created_data
from app.logging_config import get_logger

logger = get_logger(__name__)


class LeadTool:
    """Persists a CRM lead extracted from natural-language text. Called by
    the Sales employee via ToolRouter, so its signature matches ToolRouter's
    calling convention: execute(message, db, agency, conversation, lead, **kwargs).
    """

    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        message: str,
        db: Session = None,
        agency: models.Agency = None,
        conversation=None,
        lead: models.Lead = None,
        **kwargs,
    ) -> dict:
        db = db or self.db
        if agency is None:
            return {"ok": False, "error": "missing_agency"}

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
            query = db.query(models.Lead).filter(models.Lead.agency_id == agency.id)
            if phone:
                target = query.filter(models.Lead.phone == phone).first()
            if target is None and email:
                target = query.filter(models.Lead.email == email).first()
            if target is None and name:
                target = query.filter(models.Lead.name == name).first()

        # A conversation's Lead row is created empty up front (see
        # conversation_service._get_or_create_lead) and passed in here as
        # `lead` on every turn, so `target is None` alone would never be
        # true for the customer-conversation channel - the "new lead"
        # owner notification and lead_created workflow trigger would then
        # never fire for any real buyer inquiry from the website/WhatsApp/
        # Instagram widget. What actually matters is whether this is the
        # first time the lead became identifiable, not whether the row
        # itself was just inserted.
        was_unidentified = target is None or not any([target.name, target.phone, target.email])

        # Phase 10A: writes go through LeadService (the one authoritative
        # Lead-persistence path, shared with the dashboard CRUD router and
        # the marketplace inquiry flow) instead of this tool building
        # models.Lead itself. LeadCreate/LeadUpdate validate `email` as
        # EmailStr, but this value is LLM-extracted from free text, not a
        # verified address - the legacy inline path stored whatever string
        # came out with zero validation, so model_construct() is used to
        # bypass schema validation and keep that exact no-validation
        # behavior. LeadService.create() fires lead_created itself, so this
        # tool must not fire it again for the `created` branch below.
        lead_service = LeadService(db)
        created = target is None
        if created:
            payload = schemas.LeadCreate.model_construct(
                name=name, phone=phone, email=email,
                service_interested=service, budget=budget,
                buyer_id=None, property_id=None,
            )
            target = lead_service.create(agency.id, payload)
        else:
            update_fields = {}
            if name:
                update_fields["name"] = name
            if phone:
                update_fields["phone"] = phone
            if email:
                update_fields["email"] = email
            if service:
                update_fields["service_interested"] = service
            if budget:
                update_fields["budget"] = budget
            payload = schemas.LeadUpdate.model_construct(**update_fields)
            target = lead_service.update(target.id, agency.id, payload) or target

        newly_identified = was_unidentified and any([target.name, target.phone, target.email])
        if created or newly_identified:
            from app.services import notification_service

            # Idempotency: a retried call for the same lead must never
            # create a second "New lead captured" notification.
            if not notification_service.already_notified_for_lead(
                db, agency.id, target.id, models.NotificationType.new_lead,
            ):
                notification_service.create_for_agency(
                    db, agency,
                    type=models.NotificationType.new_lead,
                    title="New lead captured",
                    message=(
                        f"{target.name or 'A new lead'} is interested in "
                        f"{target.service_interested or 'your services'}."
                        f" Contact: {target.phone or target.email or 'not provided'}."
                    ),
                    event_id=str(target.id), lead_id=target.id,
                    email_event_type=notif_prefs.NEW_LEAD,
                )

            if not created:
                fire_trigger(
                    db, agency.id, models.WorkflowTriggerType.lead_created,
                    lead_created_data(target), event_id=str(target.id),
                )

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
