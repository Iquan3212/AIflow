"""
CRUD + search over Property. Two structural rules are enforced here and
nowhere else needs to re-check them:

1. Agency ownership (Step 16 of the Phase 7 spec): a Property's
   agency_id is ALWAYS copied from its parent Project, and the parent
   Project is always re-fetched scoped to the caller's own agency_id
   first - a project_id belonging to another agency simply doesn't
   resolve, so "Property.agency_id != Property.project.agency_id" has no
   code path that can ever produce it.
2. The controlled status lifecycle (status.py) plus the plan's active-
   listing cap (config.py) - both only apply when a status change is
   requested, never on plain field edits.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.services.billing.entitlement_service import EntitlementService
from app.services.inventory.status import validate_status_transition


class ProjectNotFoundError(ValueError):
    """Raised when a payload references a project_id that either doesn't
    exist or doesn't belong to the caller's own agency - deliberately the
    same error either way, so a cross-agency probe learns nothing about
    whether the id exists at all."""


class InvalidPropertyTypeError(ValueError):
    pass


class InvalidFacingError(ValueError):
    pass


class InvalidFurnishingError(ValueError):
    pass


class InvalidPropertyStatusError(ValueError):
    pass


class ListingLimitReachedError(ValueError):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(
            f"This agency's plan allows at most {limit} active listing(s) at a time. "
            "Move another listing out of 'active' first, or upgrade the plan."
        )


def _to_enum(enum_cls, value: str | None, error_cls):
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        raise error_cls(f"Unknown value: {value!r}")


class PropertyService:
    def __init__(self, db: Session):
        self.db = db

    def _get_owned_project(self, project_id: UUID, agency_id: UUID) -> models.Project:
        project = (
            self.db.query(models.Project)
            .filter(models.Project.id == project_id, models.Project.agency_id == agency_id)
            .first()
        )
        if project is None:
            raise ProjectNotFoundError(f"No project {project_id} for this agency.")
        return project

    def get(self, property_id: str, agency_id: UUID) -> models.Property | None:
        return (
            self.db.query(models.Property)
            .options(joinedload(models.Property.media))
            .filter(models.Property.id == property_id, models.Property.agency_id == agency_id)
            .first()
        )

    def create(self, agency_id: UUID, payload: schemas.PropertyCreate) -> models.Property:
        project = self._get_owned_project(payload.project_id, agency_id)  # raises if not owned

        property_type = _to_enum(models.PropertyType, payload.property_type, InvalidPropertyTypeError)
        facing = _to_enum(models.Facing, payload.facing, InvalidFacingError)
        furnishing = _to_enum(models.Furnishing, payload.furnishing, InvalidFurnishingError)

        unit = models.Property(
            agency_id=agency_id,  # always the authenticated caller's own id, never client input
            project_id=project.id,  # always the just-verified-owned project, never raw client input
            building=payload.building,
            floor=payload.floor,
            unit_number=payload.unit_number,
            property_type=property_type,
            bhk=payload.bhk,
            carpet_area_sqft=payload.carpet_area_sqft,
            built_up_area_sqft=payload.built_up_area_sqft,
            super_built_up_area_sqft=payload.super_built_up_area_sqft,
            facing=facing,
            furnishing=furnishing,
            price=payload.price,
            maintenance_amount=payload.maintenance_amount,
            possession_date=payload.possession_date,
            description=payload.description,
            rera_number=payload.rera_number,
            internal_notes=payload.internal_notes,
            status=models.PropertyStatus.draft,
        )
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def update(self, property_id: str, agency_id: UUID, payload: schemas.PropertyUpdate) -> models.Property | None:
        unit = self.get(property_id, agency_id)
        if unit is None:
            return None

        data = payload.model_dump(exclude_unset=True)
        if "property_type" in data:
            data["property_type"] = _to_enum(models.PropertyType, data["property_type"], InvalidPropertyTypeError)
        if "facing" in data:
            data["facing"] = _to_enum(models.Facing, data["facing"], InvalidFacingError)
        if "furnishing" in data:
            data["furnishing"] = _to_enum(models.Furnishing, data["furnishing"], InvalidFurnishingError)

        for key, value in data.items():
            setattr(unit, key, value)

        self.db.commit()
        self.db.refresh(unit)
        return unit

    def update_status(self, property_id: str, agency_id: UUID, new_status: str) -> models.Property | None:
        """The only path that ever changes Property.status - always
        validates the transition (status.py) and, only when moving INTO
        `active`, enforces the plan's active-listing cap (config.py)."""
        unit = self.get(property_id, agency_id)
        if unit is None:
            return None

        requested = _to_enum(models.PropertyStatus, new_status, InvalidPropertyStatusError)
        validate_status_transition(unit.status, requested)

        if requested == models.PropertyStatus.active and unit.status != models.PropertyStatus.active:
            self._enforce_active_listing_limit(agency_id)

        unit.status = requested
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def _enforce_active_listing_limit(self, agency_id: UUID) -> None:
        agency = self.db.query(models.Agency).filter(models.Agency.id == agency_id).first()
        if agency is None:
            return
        entitlements = EntitlementService(self.db)
        limit = entitlements.get_active_property_limit(agency)
        if limit is None:
            return
        if entitlements.count_active_properties(agency) >= limit:
            raise ListingLimitReachedError(limit)

    def delete(self, property_id: str, agency_id: UUID) -> bool:
        unit = self.get(property_id, agency_id)
        if unit is None:
            return False
        self.db.delete(unit)
        self.db.commit()
        return True

    def search(self, agency_id: UUID, filters: schemas.PropertyListFilters) -> list[models.Property]:
        """Pure database filtering - no LLM involved anywhere in this path
        (Step 12 of the Phase 7 spec)."""
        query = (
            self.db.query(models.Property)
            .options(joinedload(models.Property.media))
            .join(models.Project, models.Property.project_id == models.Project.id)
            .filter(models.Property.agency_id == agency_id)
        )

        conditions = []
        if filters.project_id is not None:
            conditions.append(models.Property.project_id == filters.project_id)
        if filters.status is not None:
            status = _to_enum(models.PropertyStatus, filters.status, InvalidPropertyStatusError)
            conditions.append(models.Property.status == status)
        if filters.property_type is not None:
            ptype = _to_enum(models.PropertyType, filters.property_type, InvalidPropertyTypeError)
            conditions.append(models.Property.property_type == ptype)
        if filters.bhk is not None:
            conditions.append(models.Property.bhk == filters.bhk)
        if filters.min_price is not None:
            conditions.append(models.Property.price >= filters.min_price)
        if filters.max_price is not None:
            conditions.append(models.Property.price <= filters.max_price)
        if filters.floor is not None:
            conditions.append(models.Property.floor == filters.floor)
        if filters.facing is not None:
            facing = _to_enum(models.Facing, filters.facing, InvalidFacingError)
            conditions.append(models.Property.facing == facing)
        if filters.city is not None:
            conditions.append(models.Project.city.ilike(filters.city))
        if filters.locality is not None:
            conditions.append(models.Project.locality.ilike(filters.locality))

        if conditions:
            query = query.filter(and_(*conditions))

        return query.order_by(models.Property.created_at.desc()).all()
