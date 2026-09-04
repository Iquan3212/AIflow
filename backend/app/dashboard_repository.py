from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Appointment, AppointmentStatus, Conversation, Lead, Message


class DashboardRepository:
    """Real, DB-backed dashboard figures only. No fabricated metrics -
    if something can't be honestly computed from real data yet (revenue,
    AI accuracy - no billing or feedback data exists in this schema), it
    is not reported rather than faked."""

    def __init__(self, db: Session):
        self.db = db

    def get_stats(self, business_id: str) -> dict:
        db = self.db
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())

        today_chats = (
            db.query(Conversation)
            .filter(Conversation.business_id == business_id, Conversation.started_at >= today_start)
            .count()
        )

        new_leads_today = (
            db.query(Lead)
            .filter(Lead.business_id == business_id, Lead.created_at >= today_start)
            .count()
        )

        total_leads = db.query(Lead).filter(Lead.business_id == business_id).count()

        upcoming_appointments = (
            db.query(Appointment)
            .filter(
                Appointment.business_id == business_id,
                Appointment.status == AppointmentStatus.scheduled,
                Appointment.scheduled_at >= datetime.now(),
            )
            .count()
        )

        return {
            "today_chats": today_chats,
            "new_leads_today": new_leads_today,
            "total_leads": total_leads,
            "upcoming_appointments": upcoming_appointments,
            "avg_response_time_seconds": self._avg_response_time_seconds(business_id),
            "model": get_settings().llm_model,
        }

    def _avg_response_time_seconds(self, business_id: str) -> float | None:
        """Average gap between a customer message and the AI's next reply,
        over the last 7 days. None (not 0) when there's no data yet -
        the frontend must render that as "not enough data", never as 0s."""
        since = datetime.utcnow() - timedelta(days=7)
        rows = (
            self.db.query(Message.conversation_id, Message.role, Message.created_at)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .filter(Conversation.business_id == business_id, Message.created_at >= since)
            .order_by(Message.conversation_id, Message.created_at)
            .all()
        )

        deltas: list[float] = []
        pending_user_at = None
        current_conversation = None
        for conversation_id, role, created_at in rows:
            if conversation_id != current_conversation:
                current_conversation = conversation_id
                pending_user_at = None

            if role == "user":
                pending_user_at = created_at
            elif role == "assistant" and pending_user_at is not None:
                gap = (created_at - pending_user_at).total_seconds()
                if 0 < gap <= 3600:  # ignore stale/abandoned turns as outliers
                    deltas.append(gap)
                pending_user_at = None

        if not deltas:
            return None
        return round(sum(deltas) / len(deltas), 1)
