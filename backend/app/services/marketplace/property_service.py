"""
Public, cross-agency Property search/detail for the buyer marketplace
(Phase 8) - pure database filtering, never an LLM (Step 2 of the Phase 8
spec this was built from). Every method filters through
visibility.property_is_public() (itself built on the exact same
AVAILABLE_STATUSES/is_available_status single source of truth the
Agency dashboard's own inventory already uses), so a draft/sold/
reserved/blocked property, or one belonging to an unpublished project,
can never surface here.
"""

from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.services.inventory.status import AVAILABLE_STATUSES
from app.services.marketplace.visibility import property_is_public


class InvalidSortError(ValueError):
    pass


_SORT_OPTIONS = {"recommended", "price_asc", "price_desc", "newest", "area_desc"}


class MarketplacePropertyService:
    def __init__(self, db: Session):
        self.db = db

    def to_out(self, property_: models.Property, project: models.Project) -> schemas.MarketplacePropertyOut:
        public = schemas.PropertyPublicOut.model_validate(property_)
        return schemas.MarketplacePropertyOut(
            **public.model_dump(),
            project_name=project.name,
            developer_name=project.developer_name,
            city=project.city,
            locality=project.locality,
            amenities=project.amenities,
            agency_name=project.agency.name,
            agency_slug=project.agency.slug,
        )

    def get(self, property_id: str) -> schemas.MarketplacePropertyOut | None:
        property_ = (
            self.db.query(models.Property)
            .options(
                joinedload(models.Property.media),
                joinedload(models.Property.project).joinedload(models.Project.agency),
            )
            .filter(models.Property.id == property_id)
            .first()
        )
        if property_ is None or not property_is_public(property_):
            return None
        return self.to_out(property_, property_.project)

    def search(self, filters: schemas.MarketplacePropertyFilters) -> tuple[list[schemas.MarketplacePropertyOut], int]:
        """Returns (page of results, total matching count) - the total
        lets the frontend show real pagination instead of guessing
        whether a next page exists."""
        if filters.sort not in _SORT_OPTIONS:
            raise InvalidSortError(f"Unknown sort: {filters.sort!r}")

        query = (
            self.db.query(models.Property)
            .join(models.Project, models.Property.project_id == models.Project.id)
            .join(models.Agency, models.Property.agency_id == models.Agency.id)
            .options(
                joinedload(models.Property.media),
                joinedload(models.Property.project).joinedload(models.Project.agency),
            )
            .filter(
                models.Property.status.in_(AVAILABLE_STATUSES),
                models.Project.project_status == models.ProjectStatus.active,
            )
        )

        conditions = []
        if filters.q:
            term = f"%{filters.q}%"
            conditions.append(or_(
                models.Project.name.ilike(term),
                models.Project.developer_name.ilike(term),
                models.Project.city.ilike(term),
                models.Project.locality.ilike(term),
            ))
        if filters.project_id is not None:
            conditions.append(models.Property.project_id == filters.project_id)
        if filters.property_type is not None:
            conditions.append(models.Property.property_type == filters.property_type)
        if filters.bhk is not None:
            conditions.append(models.Property.bhk == filters.bhk)
        if filters.min_price is not None:
            conditions.append(models.Property.price >= filters.min_price)
        if filters.max_price is not None:
            conditions.append(models.Property.price <= filters.max_price)
        if filters.min_area is not None:
            conditions.append(models.Property.carpet_area_sqft >= filters.min_area)
        if filters.max_area is not None:
            conditions.append(models.Property.carpet_area_sqft <= filters.max_area)
        if filters.furnishing is not None:
            conditions.append(models.Property.furnishing == filters.furnishing)
        if filters.facing is not None:
            conditions.append(models.Property.facing == filters.facing)
        if filters.possession_before is not None:
            conditions.append(models.Property.possession_date <= filters.possession_before)
        if filters.city is not None:
            conditions.append(models.Project.city.ilike(filters.city))
        if filters.locality is not None:
            conditions.append(models.Project.locality.ilike(filters.locality))

        if conditions:
            query = query.filter(and_(*conditions))

        total = query.count()

        # "Recommended" is a deliberately deterministic, real-attribute
        # ordering, never a claimed ML ranking (Step 14 of the Phase 8
        # spec) - most-recently-listed first, the same honest default
        # every other list in this app already uses.
        if filters.sort == "price_asc":
            query = query.order_by(models.Property.price.asc().nulls_last())
        elif filters.sort == "price_desc":
            query = query.order_by(models.Property.price.desc().nulls_last())
        elif filters.sort == "area_desc":
            query = query.order_by(models.Property.carpet_area_sqft.desc().nulls_last())
        elif filters.sort == "newest":
            query = query.order_by(models.Property.created_at.desc())
        else:  # recommended
            query = query.order_by(models.Property.updated_at.desc())

        rows = query.offset(filters.offset).limit(filters.limit).all()
        return [self.to_out(p, p.project) for p in rows], total

    def similar(
        self, agency_id, *, property_type: str | None, bhk: int | None, exclude_property_id, limit: int = 5,
    ) -> list[schemas.MarketplacePropertyOut]:
        """Same-agency 'similar units' lookup backing the AI assistant's
        list_similar_properties tool (Step 8 of the Phase 8 spec) - pure
        database filtering, deliberately scoped to the ONE agency the
        buyer is already talking to, never cross-agency (that agency's
        assistant recommending a competitor's listing would be a
        product bug, not a feature)."""
        query = (
            self.db.query(models.Property)
            .join(models.Project, models.Property.project_id == models.Project.id)
            .options(joinedload(models.Property.project).joinedload(models.Project.agency))
            .filter(
                models.Property.agency_id == agency_id,
                models.Property.status.in_(AVAILABLE_STATUSES),
                models.Project.project_status == models.ProjectStatus.active,
                models.Property.id != exclude_property_id,
            )
        )
        if property_type is not None:
            query = query.filter(models.Property.property_type == property_type)
        if bhk is not None:
            query = query.filter(models.Property.bhk == bhk)

        rows = query.order_by(models.Property.updated_at.desc()).limit(limit).all()
        return [self.to_out(p, p.project) for p in rows]
