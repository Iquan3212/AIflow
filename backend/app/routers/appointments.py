"""
Dashboard-facing appointment endpoints (all require the agency's auth token).
Customer-facing booking happens through the chat tools, not here.
"""

from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import to_local

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get("/", response_model=list[schemas.AppointmentOut])
def list_appointments(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return AppointmentService(db).repo.get_all(agency.id)


@router.get("/availability", response_model=schemas.AvailabilityOut)
def get_availability(
    date_local: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        y, m, d = map(int, date_local.split("-"))
        day = date(y, m, d)
    except Exception:
        raise HTTPException(status_code=400, detail="date_local must be YYYY-MM-DD")

    service = AppointmentService(db)
    slots = service.list_slots(agency, day)
    return schemas.AvailabilityOut(
        date_local=date_local,
        timezone=agency.timezone,
        slots=[
            schemas.SlotOut(
                start_local_iso=to_local(s, agency.timezone).strftime("%Y-%m-%dT%H:%M"),
                label=_label(s, agency.timezone),
            )
            for s in slots
        ],
    )


@router.post("/", response_model=schemas.AppointmentOut)
def create_appointment(
    payload: schemas.AppointmentCreate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    outcome = AppointmentService(db).book(
        agency,
        start_local_iso=payload.start_local_iso,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        service=payload.service,
        source="dashboard",
    )
    if not outcome.ok:
        raise HTTPException(status_code=409, detail={"reason": outcome.reason,
                                                     "message": outcome.message,
                                                     "alternatives": outcome.alternatives})
    return outcome.appointment


@router.put("/{appointment_id}/reschedule", response_model=schemas.AppointmentOut)
def reschedule_appointment(
    appointment_id: str,
    payload: schemas.AppointmentReschedule,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    outcome = AppointmentService(db).reschedule(agency, appointment_id, payload.new_start_local_iso)
    if not outcome.ok:
        code = 404 if outcome.reason == "not_found" else 409
        raise HTTPException(status_code=code, detail={"reason": outcome.reason,
                                                      "message": outcome.message,
                                                      "alternatives": outcome.alternatives})
    return outcome.appointment


@router.delete("/{appointment_id}")
def cancel_appointment(
    appointment_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    outcome = AppointmentService(db).cancel(agency, appointment_id)
    if not outcome.ok:
        raise HTTPException(status_code=404, detail=outcome.message)
    return {"message": outcome.message}


# ---- scheduling config (opening hours + booking rules) ----

@router.get("/settings/hours", response_model=list[schemas.BusinessHoursItem])
def get_hours(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    AppointmentService(db).ensure_defaults(agency)
    return [
        schemas.BusinessHoursItem(
            weekday=h.weekday,
            is_open=h.is_open,
            open_time=h.open_time.strftime("%H:%M") if h.open_time else None,
            close_time=h.close_time.strftime("%H:%M") if h.close_time else None,
        )
        for h in sorted(agency.business_hours, key=lambda x: x.weekday)
    ]


@router.put("/settings/hours", response_model=list[schemas.BusinessHoursItem])
def update_hours(
    payload: schemas.BusinessHoursUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    AppointmentService(db).ensure_defaults(agency)
    by_weekday = {h.weekday: h for h in agency.business_hours}
    for item in payload.hours:
        row = by_weekday.get(item.weekday)
        if row is None:
            row = models.BusinessHours(agency_id=agency.id, weekday=item.weekday)
            db.add(row)
        row.is_open = item.is_open
        row.open_time = _parse_hhmm(item.open_time)
        row.close_time = _parse_hhmm(item.close_time)
    db.commit()
    db.refresh(agency)
    return get_hours(agency, db)


@router.get("/settings/rules", response_model=schemas.SchedulingSettingsOut)
def get_rules(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    AppointmentService(db).ensure_defaults(agency)
    return agency.scheduling_settings


@router.put("/settings/rules", response_model=schemas.SchedulingSettingsOut)
def update_rules(
    payload: schemas.SchedulingSettingsUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    AppointmentService(db).ensure_defaults(agency)
    s = agency.scheduling_settings
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    h, m = map(int, value.split(":"))
    return time(h, m)


def _label(slot_utc, tz_name) -> str:
    from app.services.scheduling.datetime_utils import humanize
    return humanize(slot_utc, tz_name)
