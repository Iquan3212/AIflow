from uuid import UUID

from app.database import SessionLocal
from app.models import Lead


class LeadRepository:

    def get_all(
        self,
        business_id: UUID,
    ):
        db = SessionLocal()

        try:

            return (
                db.query(Lead)
                .filter(
                    Lead.business_id == business_id
                )
                .order_by(
                    Lead.created_at.desc()
                )
                .all()
            )

        finally:

            db.close()

    def create(
        self,
        lead: Lead,
    ):

        db = SessionLocal()

        try:

            db.add(lead)

            db.commit()

            db.refresh(lead)

            return lead

        finally:

            db.close()

    def update(
        self,
        lead_id,
        business_id,
        payload,
    ):

        db = SessionLocal()

        try:

            lead = (
                db.query(Lead)
                .filter(
                    Lead.id == lead_id,
                    Lead.business_id == business_id,
                )
                .first()
            )

            if not lead:
                return None

            for key, value in payload.items():
                setattr(
                    lead,
                    key,
                    value,
                )

            db.commit()

            db.refresh(lead)

            return lead

        finally:

            db.close()

    def delete(
        self,
        lead_id,
        business_id,
    ):

        db = SessionLocal()

        try:

            lead = (
                db.query(Lead)
                .filter(
                    Lead.id == lead_id,
                    Lead.business_id == business_id,
                )
                .first()
            )

            if not lead:
                return False

            db.delete(lead)

            db.commit()

            return True

        finally:

            db.close()