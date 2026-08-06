from datetime import datetime

from app.config import get_settings
from app.database import SessionLocal
from app.models import Conversation, Lead, Appointment


class DashboardRepository:

    def get_stats(
        self,
        business_id: str,
    ):

        db = SessionLocal()

        try:

            today = datetime.utcnow().date()
            conversations = (
                db.query(Conversation)
                .filter(Conversation.business_id == business_id)
                .filter(Conversation.started_at >= datetime.combine(today, datetime.min.time()))
                .count()
            )

            leads = (
                db.query(Lead)
                .filter(Lead.business_id == business_id)
                .filter(Lead.created_at >= datetime.combine(today, datetime.min.time()))
                .count()
            )

            appointments = (
                db.query(Appointment)
                .filter(Appointment.business_id == business_id)
                .count()
            )

            return {
                "today_chats": conversations,
                "new_leads": leads,
                "appointments": appointments,
                "revenue": 0,
                "response_time": 0,
                "accuracy": 100,
                "model": get_settings().llm_model,
                "status": "Online",
            }

        finally:

            db.close()
