"""
Monetization phase: checkout, verified activation, webhooks (signature,
idempotency, duplicate/retry handling), upgrade/downgrade, cancellation.
Uses a fake Razorpay client - never calls the real Razorpay API. Against
the real dev database with real throwaway rows, cleaned up after each
test. Zero LLM tokens.

Run: python3 -m pytest tests/test_billing_subscription_payments.py -q   (from backend/)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

import pytest

from app.database import SessionLocal
from app import models
from app.services.billing.plans import price_for
from app.services.billing.razorpay_client import PaymentsNotConfiguredError
from app.services.billing.subscription_service import (
    CheckoutNotPossibleError,
    InvalidPaymentSignatureError,
    NoSubscriptionError,
    PlanChangeBlockedError,
    SubscriptionService,
)


class FakeRazorpayClient:
    """Deterministic stand-in for RazorpayClient - never makes a real
    network call. `valid_signature` toggles whether signature
    verification succeeds, so tests can simulate a tampered/forged
    callback without needing a real Razorpay secret."""

    def __init__(self):
        self.is_configured = True
        self.key_id = "rzp_test_fake_key"
        self.valid_signature = True
        self._counter = 0
        self.cancelled_subscription_ids: list[str] = []
        self.created_plans: list[tuple] = []

    def create_plan(self, *, plan, interval, amount_rupees) -> str:
        self.created_plans.append((plan, interval, amount_rupees))
        return f"plan_fake_{plan.value}_{interval.value}"

    def create_customer(self, *, name, email) -> str:
        return f"cust_fake_{email}"

    def create_subscription(self, *, provider_plan_id, customer_id, total_count, start_at=None) -> dict:
        self._counter += 1
        return {"id": f"sub_fake_{uuid.uuid4().hex}", "plan_id": provider_plan_id, "customer_id": customer_id}

    def fetch_subscription(self, provider_subscription_id: str) -> dict:
        return {"id": provider_subscription_id, "status": "active"}

    def cancel_subscription(self, provider_subscription_id: str, *, at_cycle_end: bool = True) -> dict:
        self.cancelled_subscription_ids.append(provider_subscription_id)
        return {"id": provider_subscription_id, "status": "cancelled"}

    def verify_subscription_payment_signature(self, **kwargs) -> bool:
        return self.valid_signature

    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        return self.valid_signature


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Payments Test {suffix}",
        slug=f"payments-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@paymentstest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _cleanup(db, agency):
    db.query(models.Payment).filter(models.Payment.agency_id == agency.id).delete()
    # WebhookEvent is a provider-level ledger with no agency_id column by
    # design (see models.py) - its rows are small, harmless JSON, and
    # deliberately left in place rather than risking a delete-all that
    # could race with another test's own webhook rows.
    db.query(models.Subscription).filter(models.Subscription.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    # ProviderPlan IS global/shared with production (see _ensure_provider_plan) -
    # a fake plan_id cached here would be reused against the REAL Razorpay
    # API by real checkout traffic and rejected as invalid (confirmed: this
    # happened during real sandbox testing). Only ever delete rows this
    # FakeRazorpayClient itself created (the "plan_fake_" prefix is never
    # produced by the real RazorpayClient), never a real cached plan.
    db.query(models.ProviderPlan).filter(models.ProviderPlan.provider_plan_id.like("plan_fake_%")).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture
def env():
    db, biz = _make_agency("a")
    razorpay = FakeRazorpayClient()
    service = SubscriptionService(db, razorpay=razorpay)
    try:
        yield db, biz, razorpay, service
    finally:
        _cleanup(db, biz)


def _webhook_body(event: str, subscription_id: str, *, payment_id: str | None = None, current_start=None, current_end=None) -> str:
    subscription_entity = {"id": subscription_id}
    if current_start:
        subscription_entity["current_start"] = int(current_start.timestamp())
    if current_end:
        subscription_entity["current_end"] = int(current_end.timestamp())
    payload = {"payload": {"subscription": {"entity": subscription_entity}}}
    if payment_id:
        payload["payload"]["payment"] = {"entity": {"id": payment_id, "subscription_id": subscription_id}}
    return json.dumps({"event": event, **payload})


# ============================================================== CHECKOUT ==

class TestCheckoutCreation:
    def test_start_checkout_uses_server_side_price_never_client_supplied(self, env):
        db, biz, razorpay, service = env
        result = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        assert result["amount"] == price_for(models.SubscriptionPlan.growth, models.BillingInterval.monthly) == 10_499
        assert result["key_id"] == "rzp_test_fake_key"
        assert result["provider_subscription_id"].startswith("sub_fake_")

    def test_enterprise_cannot_self_serve_checkout(self, env):
        db, biz, razorpay, service = env
        with pytest.raises(CheckoutNotPossibleError):
            service.start_checkout(biz, models.SubscriptionPlan.enterprise, models.BillingInterval.monthly)

    def test_checkout_creates_a_trialing_subscription_row(self, env):
        db, biz, razorpay, service = env
        service.start_checkout(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)
        sub = service.get(biz)
        assert sub is not None
        assert sub.provider == "razorpay"
        assert sub.provider_subscription_id is not None

    def test_creating_a_razorpay_subscription_does_not_activate_or_change_plan(self, env):
        """The exact regression this whole test class exists to prevent:
        a Razorpay Subscription object being created (start_checkout
        alone, before Checkout even opens, let alone before payment)
        must never grant the new plan's entitlements or flip status -
        this fixture's agency has NO subscription row yet (the real,
        common case: a brand-new agency's very first checkout attempt)."""
        db, biz, razorpay, service = env
        assert service.get(biz) is None  # no subscription exists yet

        result = service.start_checkout(biz, models.SubscriptionPlan.professional, models.BillingInterval.monthly)
        assert result["provider_subscription_id"]  # a real Razorpay Subscription WAS created

        after = service.get(biz)
        assert after is not None
        assert after.plan == models.SubscriptionPlan.starter  # the safe default, NEVER "professional"
        assert after.status == models.SubscriptionStatus.trialing  # NEVER "active"
        assert after.provider_plan_id is not None  # the pending target IS tracked, just not applied yet

    def test_creating_a_razorpay_subscription_for_an_already_trialing_agency_does_not_change_its_plan(self, env):
        db, biz, razorpay, service = env
        # First checkout establishes a real subscription row (still trialing).
        service.start_checkout(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)
        before = service.get(biz)
        assert before.plan == models.SubscriptionPlan.starter
        assert before.status == models.SubscriptionStatus.trialing

        # A SECOND checkout, for a different (higher) plan, must not
        # apply that plan either - only a verified payment can.
        service.start_checkout(biz, models.SubscriptionPlan.professional, models.BillingInterval.annual)
        after = service.get(biz)
        assert after.plan == models.SubscriptionPlan.starter  # unchanged
        assert after.status == models.SubscriptionStatus.trialing  # unchanged

    def test_opening_checkout_twice_never_activates_either_attempt(self, env):
        db, biz, razorpay, service = env
        service.start_checkout(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)
        service.start_checkout(biz, models.SubscriptionPlan.professional, models.BillingInterval.annual)
        after = service.get(biz)
        assert after.status == models.SubscriptionStatus.trialing  # neither checkout activated anything

    def test_provider_plan_is_cached_not_recreated_on_second_checkout(self, env):
        db, biz, razorpay, service = env
        # ProviderPlan is a global (not agency-scoped) cache - another
        # test/run may have already created this exact (plan, interval)
        # combo's row, which would make this test's own first checkout
        # find it already cached. Start from a guaranteed-clean slate.
        db.query(models.ProviderPlan).filter(
            models.ProviderPlan.plan == models.SubscriptionPlan.growth,
            models.ProviderPlan.billing_interval == models.BillingInterval.monthly,
        ).delete()
        db.commit()

        service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        assert len(razorpay.created_plans) == 1  # second checkout reused the cached ProviderPlan row


# =============================================================== SUCCESS ==

class TestPaymentSuccess:
    def test_confirm_checkout_activates_subscription(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        sub = service.confirm_checkout(
            biz, razorpay_payment_id="pay_1",
            razorpay_subscription_id=checkout["provider_subscription_id"],
            razorpay_signature="sig_whatever_but_valid",
        )
        assert sub.status == models.SubscriptionStatus.active
        assert sub.current_period_start is not None and sub.current_period_end is not None

    def test_confirm_checkout_records_a_payment_row(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_2",
            razorpay_subscription_id=checkout["provider_subscription_id"],
            razorpay_signature="sig",
        )
        payment = db.query(models.Payment).filter(models.Payment.provider_payment_id == "pay_2").first()
        assert payment is not None
        assert payment.amount == 4_199
        assert payment.status == models.PaymentStatus.captured


# ================================================================ FAILURE ==

class TestPaymentFailure:
    def test_tampered_signature_is_rejected_and_never_activates(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        razorpay.valid_signature = False
        with pytest.raises(InvalidPaymentSignatureError):
            service.confirm_checkout(
                biz, razorpay_payment_id="pay_bad",
                razorpay_subscription_id=checkout["provider_subscription_id"],
                razorpay_signature="forged",
            )
        sub = service.get(biz)
        assert sub.status == models.SubscriptionStatus.trialing  # unchanged - never activated

    def test_confirm_checkout_rejects_a_subscription_id_that_does_not_match(self, env):
        db, biz, razorpay, service = env
        service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        with pytest.raises(NoSubscriptionError):
            service.confirm_checkout(
                biz, razorpay_payment_id="pay_x",
                razorpay_subscription_id="sub_fake_does_not_exist",
                razorpay_signature="sig",
            )

    def test_cancelled_checkout_leaves_subscription_untouched(self, env):
        """The customer closed Razorpay Checkout without paying - nothing
        ever calls confirm_checkout, so the subscription simply stays
        exactly as it was (trialing) - never a crash, never a fake
        activation."""
        db, biz, razorpay, service = env
        service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        sub = service.get(biz)
        assert sub.status == models.SubscriptionStatus.trialing


# ================================================================ WEBHOOK ==

class TestWebhookSecurity:
    def test_invalid_signature_is_rejected(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        razorpay.valid_signature = False
        body = _webhook_body("subscription.activated", checkout["provider_subscription_id"], payment_id="pay_w1")
        with pytest.raises(InvalidPaymentSignatureError):
            service.handle_webhook(body, "forged-signature")
        assert service.get(biz).status == models.SubscriptionStatus.trialing

    def test_valid_webhook_activates_subscription(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        now = datetime.utcnow()
        body = _webhook_body(
            "subscription.activated", checkout["provider_subscription_id"], payment_id="pay_w2",
            current_start=now, current_end=now + timedelta(days=30),
        )
        result = service.handle_webhook(body, "sig")
        assert result["status"] == "processed"
        assert service.get(biz).status == models.SubscriptionStatus.active

    def test_duplicate_webhook_is_idempotent(self, env):
        """The exact same delivery arriving twice (Razorpay's own retry
        behavior) must never create a second Payment row."""
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        body = _webhook_body("subscription.activated", checkout["provider_subscription_id"], payment_id="pay_w3")
        first = service.handle_webhook(body, "sig")
        second = service.handle_webhook(body, "sig")
        assert first["status"] == "processed"
        assert second["status"] == "duplicate_ignored"
        assert db.query(models.Payment).filter(models.Payment.provider_payment_id == "pay_w3").count() == 1

    def test_webhook_retry_with_same_body_does_not_double_process(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)
        body = _webhook_body("subscription.activated", checkout["provider_subscription_id"], payment_id="pay_w4")
        for _ in range(3):
            service.handle_webhook(body, "sig")
        assert db.query(models.Payment).filter(models.Payment.provider_payment_id == "pay_w4").count() == 1

    def test_webhook_for_unknown_subscription_is_ignored_not_an_error(self, env):
        db, biz, razorpay, service = env
        # Unique per run (not a fixed literal) - a fixed body would hash
        # identically across separate test runs and collide with a
        # leftover WebhookEvent row from a previous run (WebhookEvent
        # rows are deliberately never cleaned up - see _cleanup()).
        unique = uuid.uuid4().hex
        body = _webhook_body("subscription.activated", f"sub_fake_never_existed_{unique}", payment_id=f"pay_ghost_{unique}")
        result = service.handle_webhook(body, "sig")
        assert result["status"] == "processed"  # accepted, but no subscription was touched (no match)

    def test_payment_succeeds_before_webhook_reaches_the_frontend(self, env):
        """confirm_checkout (the fast client-driven path) activates
        immediately from the verified signature; the slower authoritative
        webhook for the SAME payment arriving afterward must not
        double-charge or error - the same idempotent _activate() path."""
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_race",
            razorpay_subscription_id=checkout["provider_subscription_id"],
            razorpay_signature="sig",
        )
        body = _webhook_body("subscription.activated", checkout["provider_subscription_id"], payment_id="pay_race")
        result = service.handle_webhook(body, "sig")
        assert result["status"] == "processed"
        assert db.query(models.Payment).filter(models.Payment.provider_payment_id == "pay_race").count() == 1
        assert service.get(biz).status == models.SubscriptionStatus.active

    def test_browser_closes_before_redirect_webhook_still_activates(self, env):
        """confirm_checkout is never called (the browser closed) - only
        the webhook arrives. The subscription still ends up active."""
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.professional, models.BillingInterval.monthly)
        body = _webhook_body("subscription.activated", checkout["provider_subscription_id"], payment_id="pay_no_redirect")
        service.handle_webhook(body, "sig")
        assert service.get(biz).status == models.SubscriptionStatus.active

    def test_webhook_arrives_before_the_checkout_confirm_callback(self, env):
        """The reverse ordering of test_payment_succeeds_before_webhook_
        reaches_the_frontend - the webhook (authoritative) activates
        first; the frontend's own confirm_checkout call for the SAME
        payment arriving afterward must not double-charge or error."""
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        body = _webhook_body("subscription.activated", checkout["provider_subscription_id"], payment_id="pay_webhook_first")
        service.handle_webhook(body, "sig")
        assert service.get(biz).status == models.SubscriptionStatus.active

        sub = service.confirm_checkout(
            biz, razorpay_payment_id="pay_webhook_first",
            razorpay_subscription_id=checkout["provider_subscription_id"], razorpay_signature="sig",
        )
        assert sub.status == models.SubscriptionStatus.active
        assert db.query(models.Payment).filter(models.Payment.provider_payment_id == "pay_webhook_first").count() == 1

    def test_subscription_charged_activates_and_extends_the_period(self, env):
        """subscription.charged (a renewal cycle, not the first
        activation) must go through the exact same verified _activate()
        path - never a separate, less-checked code path."""
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        now = datetime.utcnow()
        body = _webhook_body(
            "subscription.charged", checkout["provider_subscription_id"], payment_id="pay_renewal",
            current_start=now, current_end=now + timedelta(days=30),
        )
        result = service.handle_webhook(body, "sig")
        assert result["status"] == "processed"
        sub = service.get(biz)
        assert sub.status == models.SubscriptionStatus.active
        assert sub.plan == models.SubscriptionPlan.growth
        assert db.query(models.Payment).filter(models.Payment.provider_payment_id == "pay_renewal").count() == 1

    def test_payment_failed_with_no_prior_active_subscription_does_not_activate_anything(self, env):
        """payment.failed must never be able to activate a subscription -
        it can only ever move an ALREADY-active one to past_due."""
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        body = json.dumps({
            "event": "payment.failed",
            "payload": {"payment": {"entity": {
                "id": f"pay_failed_{uuid.uuid4().hex}", "subscription_id": checkout["provider_subscription_id"],
            }}},
        })
        result = service.handle_webhook(body, "sig")
        assert result["status"] == "processed"
        sub = service.get(biz)
        assert sub.status == models.SubscriptionStatus.trialing  # NOT active, NOT past_due either
        assert db.query(models.Payment).filter(models.Payment.agency_id == biz.id).count() == 0

    def test_subscription_cancelled_webhook(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_cancel_setup",
            razorpay_subscription_id=checkout["provider_subscription_id"], razorpay_signature="sig",
        )
        body = _webhook_body("subscription.cancelled", checkout["provider_subscription_id"])
        service.handle_webhook(body, "sig")
        sub = service.get(biz)
        assert sub.status == models.SubscriptionStatus.cancelled
        assert sub.cancelled_at is not None

    def test_subscription_halted_webhook_sets_past_due(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_halt_setup",
            razorpay_subscription_id=checkout["provider_subscription_id"], razorpay_signature="sig",
        )
        body = _webhook_body("subscription.halted", checkout["provider_subscription_id"])
        service.handle_webhook(body, "sig")
        assert service.get(biz).status == models.SubscriptionStatus.past_due


# ==================================================== UPGRADE / DOWNGRADE ==

class TestPlanChange:
    def test_trialing_agency_always_requires_checkout_even_for_its_first_ever_plan(self, env):
        """The exact bug reported during Razorpay sandbox testing: a
        still-trialing agency selecting a plan on the pricing page used
        to apply it directly, for free, with requires_checkout=False and
        no Razorpay Checkout ever opening. change_plan() must now always
        require a real checkout, regardless of trial status."""
        db, biz, razorpay, service = env
        result = service.change_plan(biz, models.SubscriptionPlan.professional, models.BillingInterval.monthly)
        assert result["requires_checkout"] is True
        # And critically: nothing about the agency's entitlements changed
        # as a side effect of merely calling change_plan.
        assert service.get(biz) is None or service.get(biz).plan != models.SubscriptionPlan.professional

    def test_paying_agency_changing_plan_requires_a_fresh_checkout(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_up1",
            razorpay_subscription_id=checkout["provider_subscription_id"], razorpay_signature="sig",
        )
        result = service.change_plan(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        assert result["requires_checkout"] is True
        assert checkout["provider_subscription_id"] in razorpay.cancelled_subscription_ids
        # The plan itself must still be the OLD (paid-for) one - change_plan
        # only validates + cancels the old provider subscription; it never
        # applies the new plan itself (only a verified checkout does).
        assert service.get(biz).plan == models.SubscriptionPlan.starter

    def test_start_checkout_cancels_the_old_paid_subscription_when_switching_plans(self, env):
        """start_checkout() itself (not just change_plan()) must cancel an
        existing REAL paid Razorpay subscription before creating a new
        one for a different plan, so the agency is never billed twice."""
        db, biz, razorpay, service = env
        first_checkout = service.start_checkout(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_switch1",
            razorpay_subscription_id=first_checkout["provider_subscription_id"], razorpay_signature="sig",
        )
        service.start_checkout(biz, models.SubscriptionPlan.professional, models.BillingInterval.monthly)
        assert first_checkout["provider_subscription_id"] in razorpay.cancelled_subscription_ids

    def test_invalid_downgrade_is_blocked_with_a_clear_message(self, env):
        db, biz, razorpay, service = env
        # Get the agency onto Growth for real (verified checkout), not via
        # the old free-switch shortcut this test used to rely on.
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_downgrade_setup",
            razorpay_subscription_id=checkout["provider_subscription_id"], razorpay_signature="sig",
        )
        assert service.get(biz).plan == models.SubscriptionPlan.growth

        from app.services.inventory.project_service import ProjectService
        from app import schemas as app_schemas
        for i in range(5):
            ProjectService(db).create(biz.id, app_schemas.ProjectCreate(name=f"P{i}", city="Bengaluru"))

        with pytest.raises(PlanChangeBlockedError) as exc_info:
            service.change_plan(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)
        assert "5 projects" in exc_info.value.violations[0]
        # plan must be unchanged after a blocked attempt
        assert service.get(biz).plan == models.SubscriptionPlan.growth

    def test_invalid_downgrade_is_also_blocked_directly_at_checkout(self, env):
        """The same guard must apply to start_checkout() directly, not
        just change_plan() - a client could otherwise skip change_plan
        entirely and check out for a plan its current usage doesn't fit."""
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_downgrade_setup2",
            razorpay_subscription_id=checkout["provider_subscription_id"], razorpay_signature="sig",
        )
        from app.services.inventory.project_service import ProjectService
        from app import schemas as app_schemas
        for i in range(5):
            ProjectService(db).create(biz.id, app_schemas.ProjectCreate(name=f"Q{i}", city="Bengaluru"))

        with pytest.raises(PlanChangeBlockedError):
            service.start_checkout(biz, models.SubscriptionPlan.starter, models.BillingInterval.monthly)

    def test_cannot_self_serve_change_to_enterprise(self, env):
        db, biz, razorpay, service = env
        with pytest.raises(CheckoutNotPossibleError):
            service.change_plan(biz, models.SubscriptionPlan.enterprise, models.BillingInterval.monthly)


# ==================================================================== CANCEL ==

class TestCancellation:
    def test_cancel_sets_cancel_at_period_end(self, env):
        db, biz, razorpay, service = env
        checkout = service.start_checkout(biz, models.SubscriptionPlan.growth, models.BillingInterval.monthly)
        service.confirm_checkout(
            biz, razorpay_payment_id="pay_cancel2",
            razorpay_subscription_id=checkout["provider_subscription_id"], razorpay_signature="sig",
        )
        sub = service.cancel(biz)
        assert sub.cancel_at_period_end is True
        assert sub.cancelled_at is not None
        # Still usable until the period actually ends - access isn't cut off immediately.
        assert sub.status == models.SubscriptionStatus.active

    def test_cancel_with_no_subscription_raises(self, env):
        db, biz, razorpay, service = env
        db.query(models.Subscription).filter(models.Subscription.agency_id == biz.id).delete()
        db.commit()
        with pytest.raises(NoSubscriptionError):
            service.cancel(biz)
