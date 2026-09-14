"""
Public, cross-agency Project search/detail for the buyer marketplace
(Phase 8). Deliberately does NOT depend on get_current_agency - a
marketplace query has no single owning agency, by design. Every method
filters through visibility.project_is_public() so a draft/archived
project can never surface here regardless of what filters are applied.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.services.inventory.status import AVAILABLE_STATUSES
from app.services.marketplace.visibility import project_is_public


class MarketplaceProjectService:
    def __init__(self, db: Session):
        self.db = db

    def _visible_property_count(self, project_id) -> int:
        return (
            self.db.query(func.count(models.Property.id))
            .filter(
                models.Property.project_id == project_id,
                models.Property.status.in_(AVAILABLE_STATUSES),
            )
            .scalar()
            or 0
        )

    def to_out(self, project: models.Project) -> schemas.MarketplaceProjectOut:
        count = self._visible_property_count(project.id)
        return schemas.MarketplaceProjectOut(
            id=project.id,
            name=project.name,
            developer_name=project.developer_name,
            description=project.description,
            project_type=project.project_type,
            address=project.address,
            city=project.city,
            state=project.state,
            locality=project.locality,
            postal_code=project.postal_code,
            rera_number=project.rera_number,
            possession_date=project.possession_date,
            amenities=project.amenities,
            agency_name=project.agency.name,
            agency_slug=project.agency.slug,
            # Marketplace "total" and "available" are intentionally the
            # same number - both mean "publicly visible units" here.
            # Showing a separate, larger "total" (including sold/draft/
            # archived units) would leak an agency's private inventory
            # size to every visitor; see visibility.py.
            total_properties=count,
            available_properties=count,
            media=project.media,
        )

    def search(self, filters: schemas.MarketplaceProjectFilters) -> list[schemas.MarketplaceProjectOut]:
        query = (
            self.db.query(models.Project)
            .join(models.Agency, models.Project.agency_id == models.Agency.id)
            .options(joinedload(models.Project.media), joinedload(models.Project.agency))
            .filter(models.Project.project_status == models.ProjectStatus.active)
        )

        if filters.city:
            query = query.filter(models.Project.city.ilike(filters.city))
        if filters.locality:
            query = query.filter(models.Project.locality.ilike(filters.locality))
        if filters.project_type:
            query = query.filter(models.Project.project_type == filters.project_type)
        if filters.developer:
            query = query.filter(models.Project.developer_name.ilike(f"%{filters.developer}%"))
        if filters.q:
            term = f"%{filters.q}%"
            query = query.filter(
                or_(
                    models.Project.name.ilike(term),
                    models.Project.developer_name.ilike(term),
                    models.Project.city.ilike(term),
                    models.Project.locality.ilike(term),
                )
            )

        projects = query.order_by(models.Project.created_at.desc()).all()
        return [self.to_out(p) for p in projects]

    def get(self, project_id: str) -> schemas.MarketplaceProjectDetailOut | None:
        project = (
            self.db.query(models.Project)
            .options(joinedload(models.Project.media), joinedload(models.Project.agency))
            .filter(models.Project.id == project_id)
            .first()
        )
        if project is None or not project_is_public(project):
            return None

        properties = (
            self.db.query(models.Property)
            .options(joinedload(models.Property.media))
            .filter(
                models.Property.project_id == project.id,
                models.Property.status.in_(AVAILABLE_STATUSES),
            )
            .order_by(models.Property.created_at.desc())
            .all()
        )

        base = self.to_out(project)
        from app.services.marketplace.property_service import MarketplacePropertyService

        property_service = MarketplacePropertyService(self.db)
        return schemas.MarketplaceProjectDetailOut(
            **base.model_dump(),
            properties=[property_service.to_out(p, project) for p in properties],
        )
