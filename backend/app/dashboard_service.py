from sqlalchemy.orm import Session

from app.dashboard_repository import DashboardRepository


def get_dashboard_stats(db: Session, business_id: str) -> dict:
    return DashboardRepository(db).get_stats(business_id)
