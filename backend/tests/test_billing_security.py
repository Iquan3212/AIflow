"""
Monetization phase security: billing mutations are owner-only, a buyer
token can never reach agency billing, agency A can never touch agency
B's subscription, and nothing the client sends (a plan id, an amount) is
ever trusted over server-side configuration/verification. Against the
real dev database with real throwaway rows, cleaned up after each test.
Zero LLM tokens, zero real Razorpay calls.

Run: python3 -m pytest tests/test_billing_security.py -q   (from backend/)
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models, schemas
from app.deps import get_current_agency, get_current_buyer, require_billing_owner
from app.security import create_access_token
from app.routers.billing import _to_plan, _to_interval, create_checkout, get_subscription
from app.services.billing.subscription_service import NoSubscriptionError, SubscriptionService


class FakeRazorpayClient:
    """Minimal deterministic stand-in for RazorpayClient - duplicated here
    (rather than imported from test_billing_subscription_payments.py) so
    this file has no cross-test-module import fragility; see that file
    for the full version with configurable signature verification."""

    def __init__(self):
        self.is_configured = True
        self.key_id = "rzp_test_fake_key"
        self._counter = 0

    def create_plan(self, *, plan, interval, amount_rupees) -> str:
        return f"plan_fake_{plan.value}_{interval.value}"

    def create_customer(self, *, name, email) -> str:
        return f"cust_fake_{email}"

    def create_subscription(self, *, provider_plan_id, customer_id, total_count, start_at=None) -> dict:
        self._counter += 1
        return {"id": f"sub_fake_{uuid.uuid4().hex}", "plan_id": provider_plan_id, "customer_id": customer_id}

    def cancel_subscription(self, provider_subscription_id: str, *, at_cycle_end: bool = True) -> dict:
        return {"id": provider_subscription_id, "status": "cancelled"}

    def verify_subscription_payment_signature(self, **kwargs) -> bool:
        return True

    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        return True


def _make_agency_with_user(suffix: str, role: str = "owner"):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Billing Security {suffix}",
        slug=f"billing-security-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@billingsecurity.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)

    user = models.User(agency_id=agency.id, email=f"user-{suffix}@billingsecurity.example", hashed_password="x", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return db, agency, user


def _cleanup(db, agency):
    db.query(models.Subscription).filter(models.Subscription.agency_id == agency.id).delete()
    db.query(models.User).filter(models.User.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


class TestOwnerOnlyEnforcement:
    def test_owner_can_pass(self):
        db, agency, user = _make_agency_with_user("owner", role="owner")
        try:
            result = require_billing_owner(agency=agency, user=user)
            assert result.id == agency.id
        finally:
            _cleanup(db, agency)

    def test_non_owner_role_is_rejected(self):
        db, agency, user = _make_agency_with_user("staff", role="staff")
        try:
            with pytest.raises(HTTPException) as exc_info:
                require_billing_owner(agency=agency, user=user)
            assert exc_info.value.status_code == 403
        finally:
            _cleanup(db, agency)


class TestBuyerCannotAccessBilling:
    def test_buyer_token_cannot_satisfy_get_current_agency(self):
        """A buyer's JWT has a buyer_id claim, never agency_id - the same
        structural boundary every other buyer/agency dependency already
        relies on (see test_buyer_saved_properties.py's mirror test)."""
        buyer_token = create_access_token({"buyer_id": str(uuid.uuid4()), "sub": "buyer@example.test"})
        creds = type("Creds", (), {"credentials": buyer_token})()
        db = SessionLocal()
        try:
            with pytest.raises(HTTPException) as exc_info:
                get_current_agency(credentials=creds, db=db)
            assert exc_info.value.status_code == 401
        finally:
            db.close()

    def test_agency_token_cannot_satisfy_get_current_buyer(self):
        agency_token = create_access_token({"agency_id": str(uuid.uuid4()), "sub": "owner@example.test"})
        creds = type("Creds", (), {"credentials": agency_token})()
        db = SessionLocal()
        try:
            with pytest.raises(HTTPException) as exc_info:
                get_current_buyer(credentials=creds, db=db)
            assert exc_info.value.status_code == 401
        finally:
            db.close()


class TestAgencyIsolation:
    def test_agency_a_cannot_confirm_a_checkout_using_agency_bs_provider_subscription_id(self):
        db_a, agency_a, _ = _make_agency_with_user("a")
        db_b, agency_b, _ = _make_agency_with_user("b")
        try:
            razorpay = FakeRazorpayClient()
            service_a = SubscriptionService(db_a, razorpay=razorpay)
            service_b = SubscriptionService(db_b, razorpay=razorpay)
            service_a.start_checkout(agency_a, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
            checkout_b = service_b.start_checkout(agency_b, models.SubscriptionPlan.growth, models.BillingInterval.monthly)

            # Agency A tries to claim agency B's real checkout as its own.
            with pytest.raises(Exception):
                service_a.confirm_checkout(
                    agency_a, razorpay_payment_id="pay_steal",
                    razorpay_subscription_id=checkout_b["provider_subscription_id"],
                    razorpay_signature="sig",
                )
            # B's subscription is untouched by A's attempt.
            assert service_b.get(agency_b).status == models.SubscriptionStatus.trialing
        finally:
            _cleanup(db_a, agency_a)
            _cleanup(db_b, agency_b)

    def test_get_subscription_404s_for_an_agency_with_none_rather_than_leaking_another(self):
        db, agency, _ = _make_agency_with_user("nosub")
        try:
            db.query(models.Subscription).filter(models.Subscription.agency_id == agency.id).delete()
            db.commit()
            with pytest.raises(HTTPException) as exc_info:
                get_subscription(agency=agency, db=db)
            assert exc_info.value.status_code == 404
        finally:
            _cleanup(db, agency)


class TestClientCannotTamperPricingOrPlan:
    def test_unknown_plan_id_is_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            _to_plan("gold_super_plan")
        assert exc_info.value.status_code == 422

    def test_unknown_billing_interval_is_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            _to_interval("weekly")
        assert exc_info.value.status_code == 422

    def test_checkout_request_schema_has_no_price_field_to_tamper(self):
        """The client can only ever send a plan id and an interval - there
        is no amount/price field anywhere in the request schema for a
        tampered value to even occupy; the real price always comes from
        app.services.billing.plans, computed server-side in start_checkout."""
        assert "amount" not in schemas.CheckoutRequest.model_fields
        assert "price" not in schemas.CheckoutRequest.model_fields

    def test_extra_client_supplied_amount_field_is_ignored_not_trusted(self, monkeypatch):
        db, agency, _ = _make_agency_with_user("tamper")
        try:
            payload = schemas.CheckoutRequest.model_validate({
                "plan": "starter", "billing_interval": "monthly", "amount": 1,
            })
            razorpay = FakeRazorpayClient()
            import app.routers.billing as billing_router

            monkeypatch.setattr(billing_router, "SubscriptionService", lambda db_: SubscriptionService(db_, razorpay=razorpay))
            result = create_checkout(payload, agency=agency, db=db)
            assert result["amount"] == 4_199  # the real Starter price, never the tampered "1"
        finally:
            _cleanup(db, agency)
