from uuid import UUID

from sqlalchemy.orm import Session

from app import models, schemas

from app.services.lead_ai_service import extract_lead_information   


class LeadService:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------
    # Dashboard CRUD
    # --------------------------------------------------

    def get_all(self, business_id: UUID):
        return (
            self.db.query(models.Lead)
            .filter(models.Lead.business_id == business_id)
            .order_by(models.Lead.created_at.desc())
            .all()
        )

    def create(
        self,
        business_id: UUID,
        payload: schemas.LeadCreate,
    ):

        lead = models.Lead(
            business_id=business_id,
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            service_interested=payload.service_interested,
            budget=payload.budget,
        )

        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)

        return lead

    def update(
        self,
        lead_id: UUID,
        business_id: UUID,
        payload: schemas.LeadUpdate,
    ):

        lead = (
            self.db.query(models.Lead)
            .filter(
                models.Lead.id == lead_id,
                models.Lead.business_id == business_id,
            )
            .first()
        )

        if not lead:
            return None

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(lead, key, value)

        self.db.commit()
        self.db.refresh(lead)

        return lead

    def delete(
        self,
        lead_id: UUID,
        business_id: UUID,
    ):

        lead = (
            self.db.query(models.Lead)
            .filter(
                models.Lead.id == lead_id,
                models.Lead.business_id == business_id,
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
        business_id,
        conversation_id,
        message,
    ):

        ai = extract_lead_information(message)

        lead = (
            self.db.query(models.Lead)
            .filter(
                models.Lead.business_id == business_id,
                models.Lead.conversation_id == conversation_id,
            )
            .first()
        )

        if lead is None:

            lead = models.Lead(
                business_id=business_id,
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