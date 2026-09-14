"""
Agency-side Property (unit) endpoints - all authenticated, all
agency-scoped via get_current_agency. This is the ONLY way a Property
can ever be created, changed, or have its status transitioned - status
changes go through their own endpoint so the controlled lifecycle
(app/services/inventory/status.py) is always enforced, never bypassed by
a plain field edit.

  GET    /properties                    search/filter (database-only, no LLM)
  POST   /properties                    create a unit under an owned project
  GET    /properties/{id}               one unit's full detail
  PATCH  /properties/{id}               update fields (not status)
  PUT    /properties/{id}/status        the only path that changes status
  DELETE /properties/{id}
  POST   /properties/{id}/media         upload a unit photo or floor plan
  GET    /properties/{id}/media
  GET    /properties/{id}/media/{media_id}/file   fetch the raw file bytes
  DELETE /properties/{id}/media/{media_id}
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency
from app.services.inventory.media_service import InvalidMediaUploadError, PropertyMediaService, content_type_for
from app.services.inventory.property_service import (
    InvalidFacingError,
    InvalidFurnishingError,
    InvalidPropertyStatusError,
    InvalidPropertyTypeError,
    ListingLimitReachedError,
    ProjectNotFoundError,
    PropertyService,
)
from app.services.inventory.status import InvalidStatusTransitionError

router = APIRouter(prefix="/properties", tags=["Properties"])


@router.get("", response_model=list[schemas.PropertyOut])
def search_properties(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
    project_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    property_type: str | None = Query(default=None),
    bhk: int | None = Query(default=None),
    min_price: float | None = Query(default=None),
    max_price: float | None = Query(default=None),
    city: str | None = Query(default=None),
    locality: str | None = Query(default=None),
    floor: int | None = Query(default=None),
    facing: str | None = Query(default=None),
):
    filters = schemas.PropertyListFilters(
        project_id=project_id, status=status, property_type=property_type, bhk=bhk,
        min_price=min_price, max_price=max_price, city=city, locality=locality,
        floor=floor, facing=facing,
    )
    try:
        return PropertyService(db).search(agency.id, filters)
    except (InvalidPropertyStatusError, InvalidPropertyTypeError, InvalidFacingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("", response_model=schemas.PropertyOut, status_code=201)
def create_property(
    payload: schemas.PropertyCreate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        return PropertyService(db).create(agency.id, payload)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found for this agency")
    except (InvalidPropertyTypeError, InvalidFacingError, InvalidFurnishingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{property_id}", response_model=schemas.PropertyOut)
def get_property(
    property_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    unit = PropertyService(db).get(property_id, agency.id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return unit


@router.patch("/{property_id}", response_model=schemas.PropertyOut)
def update_property(
    property_id: str,
    payload: schemas.PropertyUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        unit = PropertyService(db).update(property_id, agency.id, payload)
    except (InvalidPropertyTypeError, InvalidFacingError, InvalidFurnishingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if unit is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return unit


@router.put("/{property_id}/status", response_model=schemas.PropertyOut)
def update_property_status(
    property_id: str,
    payload: schemas.PropertyStatusUpdate,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    try:
        unit = PropertyService(db).update_status(property_id, agency.id, payload.status)
    except InvalidPropertyStatusError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ListingLimitReachedError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    if unit is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return unit


@router.delete("/{property_id}")
def delete_property(
    property_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    if not PropertyService(db).delete(property_id, agency.id):
        raise HTTPException(status_code=404, detail="Property not found")
    return {"message": "Property deleted successfully"}


# ---- property media --------------------------------------------------

@router.post("/{property_id}/media", response_model=schemas.PropertyMediaOut, status_code=201)
async def upload_property_media(
    property_id: str,
    file: UploadFile,
    media_type: str = Query(default="image", pattern="^(image|floor_plan)$"),
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    unit = PropertyService(db).get(property_id, agency.id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Property not found")

    content = await file.read()
    try:
        return PropertyMediaService(db).upload_for_property(
            agency.id, unit, file.filename or "image", content, models.PropertyMediaType(media_type),
        )
    except InvalidMediaUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{property_id}/media", response_model=list[schemas.PropertyMediaOut])
def list_property_media(
    property_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    unit = PropertyService(db).get(property_id, agency.id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return sorted(unit.media, key=lambda m: m.sort_order)


@router.get("/{property_id}/media/{media_id}/file")
def get_property_media_file(
    property_id: str,
    media_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    media = PropertyMediaService(db).get(media_id, agency.id)
    if media is None or media.property_id != property_id:
        raise HTTPException(status_code=404, detail="Media not found")
    content = PropertyMediaService(db).read_content(media)
    return Response(content=content, media_type=content_type_for(media.file_type))


@router.delete("/{property_id}/media/{media_id}")
def delete_property_media(
    property_id: str,
    media_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    media = PropertyMediaService(db).get(media_id, agency.id)
    if media is None or media.property_id != property_id:
        raise HTTPException(status_code=404, detail="Media not found")
    PropertyMediaService(db).delete(media_id, agency.id)
    return {"message": "Media deleted successfully"}
