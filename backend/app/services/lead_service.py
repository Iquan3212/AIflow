from uuid import UUID

from sqlalchemy.orm import Session

from app import models, schemas

from app.services.lead_ai_service import extract_lead_information
from app.services.workflows.triggers import fire_trigger, lead_created_data, lead_data


class LeadService:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------
    # Dashboard CRUD
    # --------------------------------------------------

    def get_all(self, agency_id: UUID):
        return (
            self.db.query(models.Lead)
            .filter(models.Lead.agency_id == agency_id)
            .order_by(models.Lead.created_at.desc())
            .all()
        )

    def get(self, lead_id: UUID, agency_id: UUID):
        return (
            self.db.query(models.Lead)
            .filter(
                models.Lead.id == lead_id,
                models.Lead.agency_id == agency_id,
            )
            .first()
        )

    def create(
        self,
        agency_id: UUID,
        payload: schemas.LeadCreate,
    ):

        lead = models.Lead(
            agency_id=agency_id,
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            service_interested=payload.service_interested,
            budget=payload.budget,
            buyer_id=payload.buyer_id,
            property_id=payload.property_id,
        )

        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)

        fire_trigger(
            self.db, agency_id, models.WorkflowTriggerType.lead_created,
            lead_created_data(lead), event_id=str(lead.id),
        )

        return lead

    def update(
        self,
        lead_id: UUID,
        agency_id: UUID,
        payload: schemas.LeadUpdate,
    ):

        lead = (
            self.db.query(models.Lead)
            .filter(
                models.Lead.id == lead_id,
                models.Lead.agency_id == agency_id,
            )
            .first()
        )

        if not lead:
            return None

        changed_fields = payload.model_dump(exclude_unset=True)
        previous_status = lead.status
        previous_score = lead.qualification_score

        for key, value in changed_fields.items():
            setattr(lead, key, value)

        self.db.commit()
        self.db.refresh(lead)

        # Phase 11: fires from the ONE generic update path both the
        # dashboard's PUT /leads/{id} and the Lead Qualification AI
        # employee's update_lead_qualification tool already go through
        # (see realestate_lead_property_tools.py) - no separate wiring
        # needed for either caller. Event ids include the new value AND
        # lead.updated_at (fresh from the commit above) so a genuine
        # repeated transition (e.g. new -> qualified -> new -> qualified)
        # is never treated as a duplicate of an earlier, different one -
        # only an identical retried call within the same commit shares an
        # id.
        if "status" in changed_fields and lead.status != previous_status:
            fire_trigger(
                self.db, agency_id, models.WorkflowTriggerType.lead_status_changed,
                lead_data(lead), event_id=f"{lead.id}:{lead.status}:{lead.updated_at.isoformat()}",
            )
        if "qualification_score" in changed_fields and lead.qualification_score != previous_score:
            fire_trigger(
                self.db, agency_id, models.WorkflowTriggerType.lead_qualified,
                lead_data(lead), event_id=f"{lead.id}:{lead.qualification_score}:{lead.updated_at.isoformat()}",
            )

        return lead

    def delete(
        self,
        lead_id: UUID,
        agency_id: UUID,
    ):

        lead = (
            self.db.query(models.Lead)
            .filter(
                models.Lead.id == lead_id,
                models.Lead.agency_id == agency_id,
            )
            .first()
        )

        if not lead:
            return False

        self.db.delete(lead)
        self.db.commit()

        return True

    # --------------------------------------------------
    # AI Lead Capture
    # --------------------------------------------------

    def process_message(
        self,
        agency_id,
        conversation_id,
        message,
    ):

        ai = extract_lead_information(message)

        lead = (
            self.db.query(models.Lead)
            .filter(
                models.Lead.agency_id == agency_id,
                models.Lead.conversation_id == conversation_id,
            )
            .first()
        )

        if lead is None:

            lead = models.Lead(
                agency_id=agency_id,
                conversation_id=conversation_id,
                status="new",
            )

            self.db.add(lead)
            self.db.commit()
            self.db.refresh(lead)

        if ai.get("name"):
            lead.name = ai["name"]

        if ai.get("phone"):
            lead.phone = ai["phone"]

        if ai.get("email"):
            lead.email = ai["email"]

        if ai.get("service_interested"):
            lead.service_interested = ai["service_interested"]

        if ai.get("budget"):
            lead.budget = ai["budget"]

        self.db.commit()
        self.db.refresh(lead)

        return {
            "lead": lead,
            "buying_intent": ai.get(
                "buying_intent",
                False,
            ),
        }
    

    # --------------------------------------------------
    # Buying Intent
    # --------------------------------------------------

    def detect_buying_intent(
        self,
        message: str,
    ):

        text = message.lower()

        keywords = [
            "buy",
            "price",
            "cost",
            "quotation",
            "quote",
            "interested",
            "book",
            "appointment",
            "service",
            "demo",
            "trial",
        ]

        return any(word in text for word in keywords)

    # --------------------------------------------------
    # Simple Information Extraction
    # --------------------------------------------------

    def extract_information(
        self,
        lead,
        message,
    ):

        import re

        if lead.phone is None:
            phone = re.search(r"\b\d{10}\b", message)

            if phone:
                lead.phone = phone.group()

        if lead.email is None:
            email = re.search(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                message,
            )

            if email:
                lead.email = email.group()