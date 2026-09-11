from sqlalchemy.orm import Session

from app.dashboard_repository import DashboardRepository


def get_dashboard_stats(db: Session, agency_id: str) -> dict:
    return DashboardRepository(db).get_stats(agency_id)
