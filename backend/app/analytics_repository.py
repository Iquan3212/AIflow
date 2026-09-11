from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Appointment, Conversation, Lead

DAYS_BACK = 14


class AnalyticsRepository:
    """Every figure here is a real COUNT/GROUP BY over real rows for this
    agency. No projected, estimated, or invented numbers."""

    def __init__(self, db: Session):
        self.db = db

    def overview(self, agency_id: str) -> dict:
        since = datetime.utcnow() - timedelta(days=DAYS_BACK)

        return {
            "leads_by_status": self._count_by(Lead, agency_id, Lead.status),
            "appointments_by_status": self._count_by(Appointment, agency_id, Appointment.status, enum_value=True),
            "leads_per_day": self._per_day(Lead, agency_id, Lead.created_at, since),
            "appointments_per_day": self._per_day(Appointment, agency_id, Appointment.scheduled_at, since),
            "conversations_per_day": self._per_day(Conversation, agency_id, Conversation.started_at, since),
            "total_leads": self.db.query(Lead).filter(Lead.agency_id == agency_id).count(),
            "total_appointments": self.db.query(Appointment).filter(Appointment.agency_id == agency_id).count(),
            "total_conversations": self.db.query(Conversation).filter(Conversation.agency_id == agency_id).count(),
        }

    def _count_by(self, model, agency_id: str, column, enum_value: bool = False) -> dict[str, int]:
        rows = (
            self.db.query(column, func.count())
            .filter(model.agency_id == agency_id)
            .group_by(column)
            .all()
        )
        result = {}
        for key, count in rows:
            label = key.value if enum_value and hasattr(key, "value") else str(key)
            result[label] = count
        return result

    def _per_day(self, model, agency_id: str, date_column, since: datetime) -> list[dict]:
        # Bucketing in Python (rather than a SQL date-cast/group-by) avoids
        # relying on dialect-specific DATE casting behavior - the row counts
        # here are small (one agency, 14 days), so this stays cheap.
        timestamps = (
            self.db.query(date_column)
            .filter(model.agency_id == agency_id, date_column >= since)
            .all()
        )
        counts = Counter(ts.date() for (ts,) in timestamps if ts is not None)

        today = datetime.utcnow().date()
        series = []
        for offset in range(DAYS_BACK - 1, -1, -1):
            day = today - timedelta(days=offset)
            series.append({"date": day.isoformat(), "count": counts.get(day, 0)})
        return series
