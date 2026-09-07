from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_business
from app.models import Business
from app.services.notifications import preferences as notif_prefs

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/preferences", response_model=list[schemas.NotificationPreferenceItem])
def get_preferences(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return notif_prefs.get_preference_matrix(db, business.id)


@router.put("/preferences", response_model=list[schemas.NotificationPreferenceItem])
def update_preferences(
    payload: schemas.NotificationPreferencesUpdateRequest,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    try:
        return notif_prefs.set_preferences(
            db, business.id, [u.model_dump() for u in payload.updates]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
