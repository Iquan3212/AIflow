"""
Buyer-scoped saved properties (Phase 8, Step 12) - authenticated via
get_current_buyer only, exactly like every other /buyer/* endpoint.
Never depends on get_current_agency; an agency token cannot satisfy
get_current_buyer either way (see app/deps.py).

  GET    /buyer/saved-properties
  POST   /buyer/saved-properties/{property_id}
  DELETE /buyer/saved-properties/{property_id}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_buyer
from app.services.marketplace.saved_property_service import PropertyNotFoundError, SavedPropertyService

router = APIRouter(prefix="/buyer/saved-properties", tags=["buyer-saved-properties"])


@router.get("", response_model=list[schemas.MarketplacePropertyOut])
def list_saved_properties(
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    return SavedPropertyService(db).list(buyer.id)


@router.post("/{property_id}", response_model=schemas.MarketplacePropertyOut, status_code=201)
def save_property(
    property_id: str,
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    try:
        return SavedPropertyService(db).save(buyer.id, property_id)
    except PropertyNotFoundError:
        raise HTTPException(status_code=404, detail="Property not found")


@router.delete("/{property_id}", status_code=204)
def remove_saved_property(
    property_id: str,
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    if not SavedPropertyService(db).remove(buyer.id, property_id):
        raise HTTPException(status_code=404, detail="Saved property not found")
    return None
