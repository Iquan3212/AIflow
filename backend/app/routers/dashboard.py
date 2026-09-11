from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_agency
from app.dashboard_service import get_dashboard_stats
from app.models import Agency

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/stats",
    response_model=schemas.DashboardStats,
)
def dashboard_stats(
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return get_dashboard_stats(db, agency.id)
