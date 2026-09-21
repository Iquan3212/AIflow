from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_agency
from app.models import Agency
from app.services import notification_service
from app.services.notifications import preferences as notif_prefs

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[schemas.NotificationOut])
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return notification_service.list_for_agency(db, agency.id, unread_only=unread_only, limit=limit, offset=offset)


@router.get("/unread-count", response_model=schemas.NotificationUnreadCountOut)
def get_unread_notification_count(
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return schemas.NotificationUnreadCountOut(unread_count=notification_service.unread_count(db, agency.id))


@router.post("/{notification_id}/read", response_model=schemas.NotificationOut)
def mark_notification_read(
    notification_id: str,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    notification = notification_service.mark_read(db, agency.id, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return notification


@router.post("/read-all", response_model=schemas.MessageResponse)
def mark_all_notifications_read(
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    count = notification_service.mark_all_read(db, agency.id)
    return schemas.MessageResponse(message=f"Marked {count} notification(s) read.")


@router.get("/preferences", response_model=list[schemas.NotificationPreferenceItem])
def get_preferences(
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return notif_prefs.get_preference_matrix(db, agency.id)


@router.put("/preferences", response_model=list[schemas.NotificationPreferenceItem])
def update_preferences(
    payload: schemas.NotificationPreferencesUpdateRequest,
    agency: Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        return notif_prefs.set_preferences(
            db, agency.id, [u.model_dump() for u in payload.updates]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
