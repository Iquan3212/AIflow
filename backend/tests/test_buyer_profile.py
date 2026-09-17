"""
Buyer UI phase: GET/PATCH /buyer/profile - a buyer can read and partially
update their own profile (personal info, search preferences, and
notification opt-outs); email is never editable here; a buyer can never
touch another buyer's row; every notification/preference field defaults
to unset/enabled so an existing buyer is unaffected until they actually
change something. Against the real dev database with real throwaway
rows, cleaned up after each test. Zero LLM tokens.

Run: python3 -m pytest tests/test_buyer_profile.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app import models, schemas
from app.routers.buyer_profile import get_profile, update_profile


def _make_buyer(suffix: str) -> tuple[SessionLocal, models.Buyer]:
    db = SessionLocal()
    buyer = models.Buyer(
        name=f"Buyer {suffix}", email=f"buyer-profile-{suffix}-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x", phone="9990001111",
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return db, buyer


def _cleanup(db, buyer):
    db.query(models.Buyer).filter(models.Buyer.id == buyer.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def env():
    db, buyer = _make_buyer("a")
    try:
        yield db, buyer
    finally:
        _cleanup(db, buyer)


class TestBuyerProfile:
    def test_get_profile_returns_defaults(self, env):
        db, buyer = env
        out = get_profile(buyer=buyer)
        assert out.email == buyer.email
        assert out.preferred_city is None
        assert out.notify_site_visit_updates is True
        assert out.notify_inquiry_updates is True
        assert out.notify_booking_updates is True
        assert out.notify_property_alerts is True

    def test_update_personal_info(self, env):
        db, buyer = env
        result = update_profile(
            schemas.BuyerProfileUpdate(name="Updated Name", phone="8880002222"),
            buyer=buyer, db=db,
        )
        assert result.name == "Updated Name"
        assert result.phone == "8880002222"
        # email is not part of the update schema at all - unaffected
        assert result.email == buyer.email

    def test_update_search_preferences(self, env):
        db, buyer = env
        result = update_profile(
            schemas.BuyerProfileUpdate(
                preferred_city="Bengaluru", preferred_locality="Whitefield", preferred_bhk=3,
                budget_min=Decimal("5000000"), budget_max=Decimal("9000000"),
                preferred_property_type="apartment", preferred_furnishing="semi_furnished",
            ),
            buyer=buyer, db=db,
        )
        assert result.preferred_city == "Bengaluru"
        assert result.preferred_bhk == 3
        assert result.budget_min == Decimal("5000000.00")
        assert result.preferred_furnishing == "semi_furnished"

    def test_update_notification_toggles_is_partial(self, env):
        db, buyer = env
        result = update_profile(
            schemas.BuyerProfileUpdate(notify_property_alerts=False),
            buyer=buyer, db=db,
        )
        assert result.notify_property_alerts is False
        # everything else untouched by the partial update
        assert result.notify_site_visit_updates is True
        assert result.notify_inquiry_updates is True
        assert result.notify_booking_updates is True

    def test_update_is_scoped_to_the_authenticated_buyer_only(self, env):
        db, buyer = env
        db2, buyer_b = _make_buyer("b")
        try:
            update_profile(schemas.BuyerProfileUpdate(name="Only Buyer A"), buyer=buyer, db=db)
            fetched_b = get_profile(buyer=buyer_b)
            assert fetched_b.name == "Buyer b"
        finally:
            _cleanup(db2, buyer_b)
