"""
Public, cross-agency buyer marketplace (Phase 8) - deliberately does NOT
depend on get_current_agency or get_current_buyer for browsing: a
marketplace search has no single owning tenant, and requiring any bearer
token to browse would defeat the point of a public marketplace. Only the
site-visit-request endpoint requires a signed-in buyer (an identified,
not anonymous, action).

  GET  /marketplace/projects                          search
  GET  /marketplace/projects/{id}                      detail + its units
  GET  /marketplace/projects/{id}/media/{mid}/file      public cover photo
  GET  /marketplace/properties                         search
  GET  /marketplace/properties/{id}                     detail
  GET  /marketplace/properties/{id}/media/{mid}/file    public photo/floor plan
  POST /marketplace/properties/{id}/site-visit          buyer-authenticated
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_buyer
from app.services.lead_service import LeadService
from app.services.marketplace.media_service import MediaNotPublicError, get_public_project_media_content, get_public_property_media_content
from app.services.marketplace.project_service import MarketplaceProjectService
from app.services.marketplace.property_service import InvalidSortError, MarketplacePropertyService
from app.services.scheduling.appointment_service import AppointmentService

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


# ---- projects -------------------------------------------------------

@router.get("/projects", response_model=list[schemas.MarketplaceProjectOut])
def search_projects(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    locality: str | None = Query(default=None),
    project_type: str | None = Query(default=None),
    developer: str | None = Query(default=None),
):
    filters = schemas.MarketplaceProjectFilters(
        q=q, city=city, locality=locality, project_type=project_type, developer=developer,
    )
    return MarketplaceProjectService(db).search(filters)


@router.get("/projects/{project_id}", response_model=schemas.MarketplaceProjectDetailOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = MarketplaceProjectService(db).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects/{project_id}/media/{media_id}/file")
def get_project_media_file(project_id: str, media_id: str, db: Session = Depends(get_db)):
    try:
        content, content_type = get_public_project_media_content(db, project_id, media_id)
    except MediaNotPublicError:
        raise HTTPException(status_code=404, detail="Media not found")
    return Response(content=content, media_type=content_type)


# ---- properties -------------------------------------------------------

@router.get("/properties", response_model=schemas.MarketplacePropertySearchOut)
def search_properties(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    locality: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    property_type: str | None = Query(default=None),
    bhk: int | None = Query(default=None),
    min_price: float | None = Query(default=None),
    max_price: float | None = Query(default=None),
    min_area: float | None = Query(default=None),
    max_area: float | None = Query(default=None),
    furnishing: str | None = Query(default=None),
    facing: str | None = Query(default=None),
    possession_before: str | None = Query(default=None),
    sort: str = Query(default="recommended"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    filters = schemas.MarketplacePropertyFilters(
        q=q, city=city, locality=locality, project_id=project_id, property_type=property_type,
        bhk=bhk, min_price=min_price, max_price=max_price, min_area=min_area, max_area=max_area,
        furnishing=furnishing, facing=facing, possession_before=possession_before,
        sort=sort, limit=limit, offset=offset,
    )
    try:
        results, total = MarketplacePropertyService(db).search(filters)
    except InvalidSortError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return schemas.MarketplacePropertySearchOut(results=results, total=total)


@router.get("/properties/{property_id}", response_model=schemas.MarketplacePropertyOut)
def get_property(property_id: str, db: Session = Depends(get_db)):
    property_ = MarketplacePropertyService(db).get(property_id)
    if property_ is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return property_


@router.get("/properties/{property_id}/media/{media_id}/file")
def get_property_media_file(property_id: str, media_id: str, db: Session = Depends(get_db)):
    try:
        content, content_type = get_public_property_media_content(db, property_id, media_id)
    except MediaNotPublicError:
        raise HTTPException(status_code=404, detail="Media not found")
    return Response(content=content, media_type=content_type)


# ---- site visit request (buyer-authenticated) ------------------------

@router.post("/properties/{property_id}/site-visit", response_model=schemas.SiteVisitRequestOut)
def request_site_visit(
    property_id: str,
    payload: schemas.SiteVisitRequest,
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    """Creates a REAL Lead + Appointment through the exact same
    AppointmentService/LeadService the agency dashboard and the AI
    receptionist already use (Step 10 of the Phase 8 spec: reuse the
    existing appointment architecture, never a duplicate one). No new
    Appointment column was added for the property reference - like
    `demo_real_estate.py`'s own site-visit rows, the listing is named in
    the free-text `service` field, the same convention this app already
    uses for 'what is this visit about'."""
    marketplace_property = MarketplacePropertyService(db).get(property_id)
    if marketplace_property is None:
        raise HTTPException(status_code=404, detail="Property not found")

    agency = db.query(models.Agency).filter(models.Agency.slug == marketplace_property.agency_slug).first()
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found")

    listing_label = f"{marketplace_property.project_name}"
    if marketplace_property.unit_number:
        listing_label += f", Unit {marketplace_property.unit_number}"
    elif marketplace_property.building:
        listing_label += f", {marketplace_property.building}"

    lead = LeadService(db).create(
        agency.id,
        schemas.LeadCreate(
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            service_interested=f"Site visit - {listing_label}",
        ),
    )

    outcome = AppointmentService(db).book(
        agency,
        start_local_iso=f"{payload.preferred_date.isoformat()}T{payload.preferred_time}",
        customer_name=payload.name,
        customer_phone=payload.phone,
        customer_email=payload.email,
        service=f"Site visit - {listing_label}",
        lead_id=lead.id,
        source="marketplace",
    )

    return schemas.SiteVisitRequestOut(
        ok=outcome.ok,
        message=outcome.message or ("Site visit requested." if outcome.ok else "Could not book that time."),
        appointment_id=outcome.appointment.id if outcome.ok and outcome.appointment else None,
    )
