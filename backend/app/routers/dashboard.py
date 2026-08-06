from fastapi import APIRouter, Depends

from app import schemas
from app.deps import get_current_business
from app.dashboard_service import get_dashboard_stats
from app.models import Business

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/stats",
    response_model=schemas.DashboardStats,
)
def dashboard_stats(
    business: Business = Depends(get_current_business),
):
    return get_dashboard_stats(business.id)