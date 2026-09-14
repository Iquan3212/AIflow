"""
Buyer marketplace -> Agency Lead bridge (Phase 9). The one and only
place a marketplace action (a plain "inquire", or a site-visit request)
resolves or creates the Lead a buyer's interest in one property maps
to - shared by both entry points so they can never accidentally create
two different Lead rows for the same (buyer, property) pair (see the DB
`uq_lead_buyer_property` constraint this relies on as a race-safety
backstop, not just the pre-check below).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.services.lead_service import LeadService
from app.services.marketplace import lead_lifecycle
from app.services.marketplace.property_service import MarketplacePropertyService


class PropertyNotPublicError(ValueError):
    """Raised when property_id doesn't resolve through the exact same
    public marketplace visibility rules every other marketplace endpoint
    uses (Phase 9 Step 30) - never a raw Property.get(). A buyer must
    never be able to attach an unpublished/private property, or one
    belonging to no currently-active project, to any agency's Lead."""


@dataclass
class MarketplaceLeadResolution:
    lead: models.Lead
    property: models.Property
    project: models.Project
    agency: models.Agency
    created: bool


def _resolve_public_property(db: Session, property_id: str) -> models.Property:
    """Re-validates through MarketplacePropertyService.get() (the exact
    visibility gate the marketplace itself uses) before ever touching
    the raw row - a property that fails this check simply does not
    exist as far as this function is concerned."""
    marketplace_property = MarketplacePropertyService(db).get(property_id)
    if marketplace_property is None:
        raise PropertyNotPublicError(f"Property {property_id} is not publicly visible")

    property_row = (
        db.query(models.Property)
        .options(joinedload(models.Property.project).joinedload(models.Project.agency))
        .filter(models.Property.id == property_id)
        .first()
    )
    if property_row is None:  # pragma: no cover - can't happen if the check above passed
        raise PropertyNotPublicError(f"Property {property_id} is not publicly visible")
    return property_row


def get_or_create_marketplace_lead(db: Session, buyer: models.Buyer, property_id: str) -> MarketplaceLeadResolution:
    """Resolves `property_id` publicly, then finds-or-creates the ONE
    Lead for (buyer.id, property_id):
    - an existing Lead is returned as-is, except a `lost` one is
      reactivated to `new` (renewed interest, not noise - Phase 9 Step 4)
    - a genuinely new Lead is created via the existing
      LeadService.create() (so its existing lead_created workflow
      trigger fires exactly as it always has - Phase 9 Step 5) - never
      re-fired for a reused Lead.
    `agency_id` is always derived from the property's own agency, never
    accepted from anywhere the caller could influence."""
    property_row = _resolve_public_property(db, property_id)
    project_row = property_row.project
    agency = project_row.agency

    existing = (
        db.query(models.Lead)
        .filter(models.Lead.buyer_id == buyer.id, models.Lead.property_id == property_id)
        .first()
    )
    if existing is not None:
        if lead_lifecycle.reactivate_if_lost(existing):
            db.commit()
            db.refresh(existing)
        return MarketplaceLeadResolution(existing, property_row, project_row, agency, created=False)

    unit_label = " ".join(filter(None, [
        property_row.building,
        f"Unit {property_row.unit_number}" if property_row.unit_number else None,
    ]))
    service_interested = project_row.name + (f", {unit_label}" if unit_label else "")

    try:
        lead = LeadService(db).create(
            agency.id,
            schemas.LeadCreate(
                name=buyer.name, phone=buyer.phone, email=buyer.email,
                service_interested=service_interested,
                buyer_id=buyer.id, property_id=property_id,
            ),
        )
        return MarketplaceLeadResolution(lead, property_row, project_row, agency, created=True)
    except IntegrityError:
        # Lost the race to a concurrent request creating the same
        # (buyer, property) lead - the uq_lead_buyer_property constraint
        # is the actual guarantee; fall back to the row it just let
        # someone else create rather than erroring the buyer's request.
        db.rollback()
        existing = (
            db.query(models.Lead)
            .filter(models.Lead.buyer_id == buyer.id, models.Lead.property_id == property_id)
            .first()
        )
        if existing is None:  # pragma: no cover - genuinely shouldn't happen
            raise
        return MarketplaceLeadResolution(existing, property_row, project_row, agency, created=False)
