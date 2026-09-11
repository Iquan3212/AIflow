from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.analytics_repository import AnalyticsRepository
from app.database import get_db
from app.deps import get_current_agency
from app.models import Agency

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=schemas.AnalyticsOverview)
def analytics_overview(
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return AnalyticsRepository(db).overview(agency.id)
