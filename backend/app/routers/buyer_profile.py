"""
Buyer's own account/profile - Buyer UI phase. Authenticated via
get_current_buyer only, exactly like every other /buyer/* endpoint;
never accepts a buyer_id from the client.

  GET   /buyer/profile
  PATCH /buyer/profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_buyer

router = APIRouter(prefix="/buyer/profile", tags=["buyer-profile"])


@router.get("", response_model=schemas.BuyerProfileOut)
def get_profile(buyer: models.Buyer = Depends(get_current_buyer)):
    return buyer


@router.patch("", response_model=schemas.BuyerProfileOut)
def update_profile(
    payload: schemas.BuyerProfileUpdate,
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(buyer, field, value)
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer
