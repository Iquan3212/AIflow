"""
Buyer-scoped saved properties (Phase 8, Step 12): a buyer can save/list/
remove; a duplicate save is prevented (not a second row, not an error);
buyer A can never modify buyer B's saved records; unauthenticated
requests are rejected. Against the real dev database with real
throwaway rows, cleaned up after each test. Zero LLM tokens.

Run: python3 -m pytest tests/test_buyer_saved_properties.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models, schemas
from app.deps import get_current_agency, get_current_buyer
from app.security import create_access_token
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.marketplace.saved_property_service import PropertyNotFoundError, SavedPropertyService


def _make_agency_with_active_property() -> tuple[SessionLocal, models.Agency, models.Property]:
    db = SessionLocal()
    agency = models.Agency(
        name="Saved Property Test Agency",
        slug=f"saved-prop-test-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{uuid.uuid4().hex[:6]}@savedproptest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)

    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="Test Project", city="Bengaluru"))
    ProjectService(db).update(project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
    unit = PropertyService(db).create(
        agency.id,
        schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=2,
            carpet_area_sqft=Decimal("1000.00"), price=Decimal("8000000.00"), unit_number="U-1",
        ),
    )
    PropertyService(db).update_status(unit.id, agency.id, "active")
    return db, agency, unit


def _make_buyer(db, suffix: str) -> models.Buyer:
    buyer = models.Buyer(name=f"Buyer {suffix}", email=f"buyer-{suffix}-{uuid.uuid4().hex[:8]}@example.test", hashed_password="x")
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


def _cleanup(db, agency, buyers=()):
    db.query(models.BuyerSavedProperty).filter(
        models.BuyerSavedProperty.buyer_id.in_([b.id for b in buyers]) if buyers else False
    ).delete(synchronize_session=False)
    for b in buyers:
        db.query(models.Buyer).filter(models.Buyer.id == b.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def setup():
    db, agency, unit = _make_agency_with_active_property()
    buyer_a = _make_buyer(db, "a")
    buyer_b = _make_buyer(db, "b")
    try:
        yield db, agency, unit, buyer_a, buyer_b
    finally:
        _cleanup(db, agency, [buyer_a, buyer_b])


class TestSavedProperties:
    def test_buyer_can_save(self, setup):
        db, agency, unit, buyer_a, buyer_b = setup
        result = SavedPropertyService(db).save(buyer_a.id, unit.id)
        assert str(result.id) == unit.id
        saved = SavedPropertyService(db).list(buyer_a.id)
        assert [str(s.id) for s in saved] == [unit.id]

    def test_duplicate_save_is_prevented(self, setup):
        db, agency, unit, buyer_a, buyer_b = setup
        SavedPropertyService(db).save(buyer_a.id, unit.id)
        SavedPropertyService(db).save(buyer_a.id, unit.id)
        rows = (
            db.query(models.BuyerSavedProperty)
            .filter(models.BuyerSavedProperty.buyer_id == buyer_a.id, models.BuyerSavedProperty.property_id == unit.id)
            .all()
        )
        assert len(rows) == 1

    def test_buyer_can_remove(self, setup):
        db, agency, unit, buyer_a, buyer_b = setup
        SavedPropertyService(db).save(buyer_a.id, unit.id)
        assert SavedPropertyService(db).remove(buyer_a.id, unit.id) is True
        assert SavedPropertyService(db).list(buyer_a.id) == []

    def test_removing_a_never_saved_property_returns_false(self, setup):
        db, agency, unit, buyer_a, buyer_b = setup
        assert SavedPropertyService(db).remove(buyer_a.id, unit.id) is False

    def test_saving_a_nonexistent_or_unpublished_property_raises(self, setup):
        db, agency, unit, buyer_a, buyer_b = setup
        with pytest.raises(PropertyNotFoundError):
            SavedPropertyService(db).save(buyer_a.id, str(uuid.uuid4()))

    def test_buyer_a_cannot_see_buyer_bs_saved_properties(self, setup):
        db, agency, unit, buyer_a, buyer_b = setup
        SavedPropertyService(db).save(buyer_a.id, unit.id)
        assert SavedPropertyService(db).list(buyer_b.id) == []

    def test_buyer_a_cannot_remove_buyer_bs_saved_property(self, setup):
        db, agency, unit, buyer_a, buyer_b = setup
        SavedPropertyService(db).save(buyer_a.id, unit.id)
        assert SavedPropertyService(db).remove(buyer_b.id, unit.id) is False
        # buyer A's save must have survived buyer B's attempt
        assert [str(s.id) for s in SavedPropertyService(db).list(buyer_a.id)] == [unit.id]

    def test_unauthenticated_request_rejected_by_get_current_buyer(self, setup):
        """Mirrors test_inventory.py's TestBuyerCannotManageInventory - the
        same structural boundary applies here: no buyer_id claim, no access."""
        db, agency, unit, buyer_a, buyer_b = setup
        agency_token = create_access_token({"agency_id": agency.id, "sub": agency.contact_email})
        creds = type("Creds", (), {"credentials": agency_token})()
        with pytest.raises(HTTPException) as exc_info:
            get_current_buyer(credentials=creds, db=db)
        assert exc_info.value.status_code == 401

        garbage_creds = type("Creds", (), {"credentials": "not-a-real-token"})()
        with pytest.raises(HTTPException) as exc_info2:
            get_current_buyer(credentials=garbage_creds, db=db)
        assert exc_info2.value.status_code == 401
