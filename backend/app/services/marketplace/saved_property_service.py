"""
Buyer-scoped saved properties (Phase 8, Step 12). Every query filters by
buyer_id - the same structural tenant-isolation discipline every other
per-owner table in this codebase already uses - so buyer A can never
read, create under, or delete buyer B's row. Reuses
MarketplacePropertyService.to_out() so a saved property renders with the
exact same public-safe shape as the rest of the marketplace, never a
second, less-safe response shape.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.services.marketplace.property_service import MarketplacePropertyService
from app.services.marketplace.visibility import property_is_public


class PropertyNotFoundError(ValueError):
    """Raised when the target property doesn't exist, or isn't currently
    publicly visible - deliberately the same error either way, so a
    buyer can never use this endpoint to probe for hidden/unpublished
    property ids."""


class SavedPropertyService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, buyer_id: UUID) -> list[schemas.MarketplacePropertyOut]:
        saves = (
            self.db.query(models.BuyerSavedProperty)
            .options(
                joinedload(models.BuyerSavedProperty.property).joinedload(models.Property.media),
                joinedload(models.BuyerSavedProperty.property).joinedload(models.Property.project).joinedload(models.Project.agency),
            )
            .filter(models.BuyerSavedProperty.buyer_id == buyer_id)
            .order_by(models.BuyerSavedProperty.created_at.desc())
            .all()
        )
        service = MarketplacePropertyService(self.db)
        out = []
        for save in saves:
            prop = save.property
            # A save persists even if the property later goes sold/
            # unpublished - it's simply not resurfaced here until/unless
            # it becomes public again (Step 12: "property must still be
            # published/available to appear publicly").
            if prop is not None and property_is_public(prop):
                out.append(service.to_out(prop, prop.project))
        return out

    def save(self, buyer_id: UUID, property_id: str) -> schemas.MarketplacePropertyOut:
        existing = (
            self.db.query(models.BuyerSavedProperty)
            .filter(models.BuyerSavedProperty.buyer_id == buyer_id, models.BuyerSavedProperty.property_id == property_id)
            .first()
        )
        service = MarketplacePropertyService(self.db)
        if existing is not None:
            out = service.get(property_id)
            if out is None:
                raise PropertyNotFoundError(f"No public property {property_id}")
            return out

        out = service.get(property_id)  # raises nothing; returns None if not public
        if out is None:
            raise PropertyNotFoundError(f"No public property {property_id}")

        save = models.BuyerSavedProperty(buyer_id=buyer_id, property_id=property_id)
        self.db.add(save)
        self.db.commit()
        return out

    def remove(self, buyer_id: UUID, property_id: str) -> bool:
        save = (
            self.db.query(models.BuyerSavedProperty)
            .filter(models.BuyerSavedProperty.buyer_id == buyer_id, models.BuyerSavedProperty.property_id == property_id)
            .first()
        )
        if save is None:
            return False
        self.db.delete(save)
        self.db.commit()
        return True
