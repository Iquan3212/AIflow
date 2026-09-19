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
  POST /marketplace/properties/{id}/inquire              buyer-authenticated
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_buyer
from app.services.marketplace.inquiry_service import PropertyNotPublicError, get_or_create_marketplace_lead
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


# ---- inquiry + site visit request (buyer-authenticated) --------------

@router.post("/properties/{property_id}/inquire", response_model=schemas.InquiryResponse)
def inquire_about_property(
    property_id: str,
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    """The lightweight "I'm interested" action (Phase 9, Step 6) - get-or-
    creates the ONE Lead for (buyer, property) via
    get_or_create_marketplace_lead, which re-resolves the property
    through the exact same public marketplace visibility rules every
    other marketplace endpoint uses (never a raw Property.get - Step
    30), so a buyer can never attach an unpublished/private property to
    an agency's Lead this way. Never exposes the agency's own LeadOut
    to the buyer - only a safe, purpose-built response."""
    try:
        resolution = get_or_create_marketplace_lead(db, buyer, property_id)
    except PropertyNotPublicError:
        raise HTTPException(status_code=404, detail="Property not found")

    property_out = MarketplacePropertyService(db).to_out(resolution.property, resolution.project)

    message = (
        "Thanks for your interest — the agency has been notified."
        if resolution.created
        else "You've already inquired about this property — the agency has your details."
    )
    return schemas.InquiryResponse(
        success=True, message=message, inquiry_id=resolution.lead.id, property=property_out,
    )


@router.post("/properties/{property_id}/site-visit", response_model=schemas.SiteVisitRequestOut)
def request_site_visit(
    property_id: str,
    payload: schemas.SiteVisitRequest,
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    """Creates/reuses ONE Lead via the exact same get_or_create_marketplace_lead
    an inquiry uses (Phase 9, Step 7 - fixes Phase 8's bug of creating a
    brand-new Lead on every single request), then books through the
    EXISTING AppointmentService.book() unchanged - business-hours
    validation, double-booking checks, calendar sync, customer
    confirmation notification, and the appointment_created workflow
    trigger all keep working exactly as they did before Phase 9."""
    try:
        resolution = get_or_create_marketplace_lead(db, buyer, property_id)
    except PropertyNotPublicError:
        raise HTTPException(status_code=404, detail="Property not found")

    lead, property_row, project_row, agency = (
        resolution.lead, resolution.property, resolution.project, resolution.agency,
    )
    listing_label = project_row.name
    if property_row.unit_number:
        listing_label += f", Unit {property_row.unit_number}"
    elif property_row.building:
        listing_label += f", {property_row.building}"

    outcome = AppointmentService(db).book(
        agency,
        start_local_iso=f"{payload.preferred_date.isoformat()}T{payload.preferred_time}",
        customer_name=payload.name or lead.name,
        customer_phone=payload.phone or lead.phone,
        customer_email=payload.email or lead.email,
        service=f"Site visit - {listing_label}",
        lead_id=lead.id,
        source="marketplace",
        buyer_id=buyer.id,
        property_id=property_id,
    )

    # Lead -> site_visit_scheduled now happens inside AppointmentService.book()
    # itself (Final Hardening) - covers every caller that creates a real,
    # lead-linked appointment, not just this one endpoint.

    return schemas.SiteVisitRequestOut(
        ok=outcome.ok,
        message=outcome.message or ("Site visit requested." if outcome.ok else "Could not book that time."),
        appointment_id=outcome.appointment.id if outcome.ok and outcome.appointment else None,
    )
