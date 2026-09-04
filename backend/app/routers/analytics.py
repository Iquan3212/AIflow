from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.analytics_repository import AnalyticsRepository
from app.database import get_db
from app.deps import get_current_business
from app.models import Business

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=schemas.AnalyticsOverview)
def analytics_overview(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return AnalyticsRepository(db).overview(business.id)
