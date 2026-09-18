"""
CRUD over Project - mirrors LeadService/KnowledgeService's shape. Every
method is agency_id-scoped; nothing here ever queries or mutates a row
without that filter, which is what makes tenant isolation structural
rather than something each call site has to remember (Step 16 of the
Phase 7 spec).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.billing.entitlement_service import EntitlementService
from app.services.inventory.config import CANONICAL_AMENITIES
from app.services.inventory.status import is_available_status


class InvalidAmenityError(ValueError):
    def __init__(self, invalid: list[str]):
        self.invalid = invalid
        super().__init__(f"Unknown amenities: {', '.join(invalid)}")


class InvalidProjectTypeError(ValueError):
    pass


class InvalidProjectStatusError(ValueError):
    pass


def _validate_amenities(amenities: list[str] | None) -> None:
    if not amenities:
        return
    invalid = [a for a in amenities if a not in CANONICAL_AMENITIES]
    if invalid:
        raise InvalidAmenityError(invalid)


def _to_project_type(value: str | None) -> models.PropertyType | None:
    if value is None:
        return None
    try:
        return models.PropertyType(value)
    except ValueError:
        raise InvalidProjectTypeError(f"Unknown project_type: {value!r}")


def _to_project_status(value: str | None) -> models.ProjectStatus | None:
    if value is None:
        return None
    try:
        return models.ProjectStatus(value)
    except ValueError:
        raise InvalidProjectStatusError(f"Unknown project_status: {value!r}")


class ProjectService:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, agency_id: UUID) -> list[models.Project]:
        return (
            self.db.query(models.Project)
            .filter(models.Project.agency_id == agency_id)
            .order_by(models.Project.created_at.desc())
            .all()
        )

    def get(self, project_id: str, agency_id: UUID) -> models.Project | None:
        return (
            self.db.query(models.Project)
            .filter(models.Project.id == project_id, models.Project.agency_id == agency_id)
            .first()
        )

    def get_with_counts(self, agency_id: UUID) -> list[tuple[models.Project, int, int]]:
        """One row per project with its total/available property counts,
        computed in the database rather than N+1 Python loops."""
        projects = self.get_all(agency_id)
        if not projects:
            return []
        counts = dict(
            self.db.query(models.Property.project_id, func.count(models.Property.id))
            .filter(models.Property.agency_id == agency_id)
            .group_by(models.Property.project_id)
            .all()
        )
        available_counts = dict(
            self.db.query(models.Property.project_id, func.count(models.Property.id))
            .filter(
                models.Property.agency_id == agency_id,
                models.Property.status == models.PropertyStatus.active,
            )
            .group_by(models.Property.project_id)
            .all()
        )
        return [
            (p, counts.get(p.id, 0), available_counts.get(p.id, 0))
            for p in projects
        ]

    def create(self, agency_id: UUID, payload: schemas.ProjectCreate) -> models.Project:
        _validate_amenities(payload.amenities)
        project_type = _to_project_type(payload.project_type)

        agency = self.db.query(models.Agency).filter(models.Agency.id == agency_id).first()
        if agency is not None:
            EntitlementService(self.db).can_create_project(agency)

        project = models.Project(
            agency_id=agency_id,
            name=payload.name,
            developer_name=payload.developer_name,
            description=payload.description,
            project_type=project_type,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            locality=payload.locality,
            postal_code=payload.postal_code,
            latitude=payload.latitude,
            longitude=payload.longitude,
            rera_number=payload.rera_number,
            possession_date=payload.possession_date,
            amenities=payload.amenities,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update(self, project_id: str, agency_id: UUID, payload: schemas.ProjectUpdate) -> models.Project | None:
        project = self.get(project_id, agency_id)
        if project is None:
            return None

        data = payload.model_dump(exclude_unset=True)
        if "amenities" in data:
            _validate_amenities(data["amenities"])
        if "project_type" in data:
            data["project_type"] = _to_project_type(data["project_type"])
        if "project_status" in data:
            data["project_status"] = _to_project_status(data["project_status"])

        for key, value in data.items():
            setattr(project, key, value)

        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, project_id: str, agency_id: UUID) -> bool:
        """Archives rather than hard-deletes if the project still has any
        non-archived properties - a project with live inventory should
        never silently disappear along with its units' history. A project
        with no properties at all (or all already archived) can be
        deleted outright."""
        project = self.get(project_id, agency_id)
        if project is None:
            return False

        has_active_inventory = (
            self.db.query(models.Property)
            .filter(
                models.Property.project_id == project.id,
                models.Property.status != models.PropertyStatus.archived,
            )
            .first()
            is not None
        )
        if has_active_inventory:
            project.project_status = models.ProjectStatus.archived
            self.db.commit()
            return True

        self.db.delete(project)
        self.db.commit()
        return True

    def inventory_summary(self, project_id: str, agency_id: UUID) -> dict:
        properties = (
            self.db.query(models.Property)
            .filter(models.Property.project_id == project_id, models.Property.agency_id == agency_id)
            .all()
        )
        return {
            "total_properties": len(properties),
            "available_properties": sum(1 for p in properties if is_available_status(p.status)),
            "by_status": {
                status.value: sum(1 for p in properties if p.status == status)
                for status in models.PropertyStatus
            },
        }
