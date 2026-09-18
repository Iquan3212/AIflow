"""
Agency <-> Razorpay subscription lifecycle: checkout creation, verified
activation (both the immediate checkout-confirmation path and the
authoritative webhook path converge on the same idempotent _activate()),
upgrade/downgrade, and cancellation.

Never trusts a plan id, price, or "payment succeeded" claim from the
frontend - the server looks up the real price from
app.services.billing.plans, and activation only ever happens after a
verified Razorpay signature (checkout confirm) or a verified webhook.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import models
from app.models import BillingInterval, SubscriptionPlan, SubscriptionStatus
from app.services.billing.entitlement_service import EntitlementService
from app.services.billing.plans import TRIAL_DAYS, price_for
from app.services.billing.razorpay_client import PaymentsNotConfiguredError, RazorpayClient, get_razorpay_client

# A Razorpay subscription object needs a finite number of billing cycles
# up front - a generous 10-year ceiling (120 monthly cycles / 10 annual
# ones) rather than a real "infinite" option, which Razorpay's API
# doesn't offer. Renewing past this is out of scope for this phase.
_MONTHLY_CYCLE_COUNT = 120
_ANNUAL_CYCLE_COUNT = 10


class CheckoutNotPossibleError(ValueError):
    pass


class PlanChangeBlockedError(ValueError):
    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__(" ".join(violations))


class NoSubscriptionError(ValueError):
    pass


class InvalidPaymentSignatureError(ValueError):
    def __init__(self):
        super().__init__("Payment signature verification failed.")


def _period_end(start: datetime, interval: BillingInterval) -> datetime:
    return start + (timedelta(days=30) if interval == BillingInterval.monthly else timedelta(days=365))


class SubscriptionService:
    def __init__(self, db: Session, razorpay: RazorpayClient | None = None):
        self.db = db
        self.razorpay = razorpay or get_razorpay_client()
        self.entitlements = EntitlementService(db)

    def get(self, agency: models.Agency) -> models.Subscription | None:
        return self.entitlements.get_subscription(agency)

    # ---- provider plan id cache (created lazily, never a manual dashboard
    # setup step - see models.ProviderPlan) --------------------------------

    def _ensure_provider_plan(self, plan: SubscriptionPlan, interval: BillingInterval) -> str:
        row = (
            self.db.query(models.ProviderPlan)
            .filter(
                models.ProviderPlan.provider == "razorpay",
                models.ProviderPlan.plan == plan,
                models.ProviderPlan.billing_interval == interval,
            )
            .first()
        )
        if row is not None:
            return row.provider_plan_id

        amount = price_for(plan, interval)
        if amount is None:
            raise CheckoutNotPossibleError(f"{plan.value} has no public self-serve price.")
        provider_plan_id = self.razorpay.create_plan(plan=plan, interval=interval, amount_rupees=amount)
        row = models.ProviderPlan(
            provider="razorpay", plan=plan, billing_interval=interval, provider_plan_id=provider_plan_id,
        )
        self.db.add(row)
        self.db.commit()
        return provider_plan_id

    # ---- checkout ------------------------------------------------------------

    def start_checkout(self, agency: models.Agency, plan: SubscriptionPlan, interval: BillingInterval) -> dict:
        """Creates (or reuses) a Razorpay Customer + Subscription and
        returns exactly what the frontend needs to open Razorpay
        Checkout. The price is looked up here, server-side, from
        app.services.billing.plans - the client only ever sends which
        plan/interval it wants, never an amount.

        CRITICAL: creating a Razorpay Subscription object is not proof of
        payment. This method must NEVER write the entitlement-bearing
        `subscription.plan`/`billing_interval` fields - only
        `provider_plan_id` (a plain reference, not itself entitlement-
        bearing). The real plan/interval are applied only inside
        _activate(), resolved FROM provider_plan_id, only after a
        verified checkout confirmation or webhook - see that method."""
        if plan == SubscriptionPlan.enterprise:
            raise CheckoutNotPossibleError("Enterprise plans go through Contact Sales, not self-serve checkout.")

        amount = price_for(plan, interval)
        if amount is None:
            raise CheckoutNotPossibleError(f"{plan.value} has no public self-serve price.")

        # The downgrade/usage guard must apply here too, not just inside
        # change_plan() - this is the ONLY path that used to be able to
        # skip it entirely (a still-trialing agency's very first checkout).
        violations = self.entitlements.validate_plan_change(agency, plan)
        if violations:
            raise PlanChangeBlockedError(violations)

        provider_plan_id = self._ensure_provider_plan(plan, interval)

        subscription = self.get(agency)

        # Switching plans while already really paying for a DIFFERENT
        # Razorpay plan - cancel that old subscription first so the
        # agency is never billed for two plans at once. Never touches
        # local plan/status - only _activate() ever changes those, and
        # only after the NEW checkout is itself verified.
        if (
            subscription is not None
            and subscription.status in (SubscriptionStatus.active, SubscriptionStatus.past_due)
            and subscription.provider_subscription_id
            and subscription.provider_plan_id != provider_plan_id
            and self.razorpay.is_configured
        ):
            try:
                self.razorpay.cancel_subscription(subscription.provider_subscription_id, at_cycle_end=False)
            except PaymentsNotConfiguredError:
                pass

        customer_id = subscription.provider_customer_id if subscription else None
        if not customer_id:
            customer_id = self.razorpay.create_customer(name=agency.name, email=agency.contact_email)

        trial_end = None
        if subscription is not None and subscription.status == SubscriptionStatus.trialing and subscription.trial_end:
            if subscription.trial_end > datetime.utcnow():
                trial_end = subscription.trial_end

        total_count = _MONTHLY_CYCLE_COUNT if interval == BillingInterval.monthly else _ANNUAL_CYCLE_COUNT
        provider_subscription = self.razorpay.create_subscription(
            provider_plan_id=provider_plan_id, customer_id=customer_id, total_count=total_count, start_at=trial_end,
        )

        if subscription is None:
            # Every real agency already gets a Subscription row at signup
            # (see routers/auth.py) - this branch is a defensive fallback
            # for a legacy/pre-billing agency with none yet, not the
            # normal path. Deliberately defaults to the LOWEST tier
            # (Starter), never the plan being checked out - the same
            # "never grant entitlements before payment" rule this whole
            # method exists to enforce applies here too.
            subscription = models.Subscription(agency_id=agency.id, plan=SubscriptionPlan.starter, billing_interval=BillingInterval.monthly)
        # Deliberately NOT touching subscription.plan/billing_interval/status
        # here - see docstring. Only provider-reference fields.
        subscription.provider = "razorpay"
        subscription.provider_customer_id = customer_id
        subscription.provider_subscription_id = provider_subscription["id"]
        subscription.provider_plan_id = provider_plan_id
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)

        return {
            "provider_subscription_id": provider_subscription["id"],
            "key_id": self.razorpay.key_id,
            "amount": amount,
            "currency": "INR",
            "plan": plan.value,
            "billing_interval": interval.value,
        }

    def confirm_checkout(
        self, agency: models.Agency, *, razorpay_payment_id: str, razorpay_subscription_id: str, razorpay_signature: str,
    ) -> models.Subscription:
        """The immediate, client-driven confirmation path - verifies the
        real cryptographic signature Razorpay Checkout hands back (never
        a bare "success" flag) before activating anything. Safe to run
        even if the authoritative webhook for the same payment arrives
        first, or never arrives at all (browser closed before redirect) -
        _activate() is idempotent either way."""
        subscription = self.get(agency)
        if subscription is None or subscription.provider_subscription_id != razorpay_subscription_id:
            raise NoSubscriptionError("No matching checkout in progress for this agency.")

        if not self.razorpay.verify_subscription_payment_signature(
            razorpay_payment_id=razorpay_payment_id,
            razorpay_subscription_id=razorpay_subscription_id,
            razorpay_signature=razorpay_signature,
        ):
            raise InvalidPaymentSignatureError()

        now = datetime.utcnow()
        self._activate(subscription, provider_payment_id=razorpay_payment_id, period_start=now)
        return subscription

    def _activate(
        self, subscription: models.Subscription, *,
        provider_payment_id: str | None, period_start: datetime, period_end: datetime | None = None,
    ) -> None:
        """The ONLY place Subscription.status is ever set to `active`,
        and the only place `plan`/`billing_interval` change as a result
        of a checkout (never inside start_checkout - a Razorpay
        Subscription object existing is not proof of payment; see that
        method's docstring). The real plan/interval are resolved here,
        from `provider_plan_id` via the ProviderPlan cache - server-side
        data set by OUR OWN earlier start_checkout call, never anything
        a client could influence at confirmation time."""
        if subscription.provider_plan_id:
            provider_plan = (
                self.db.query(models.ProviderPlan)
                .filter(
                    models.ProviderPlan.provider == "razorpay",
                    models.ProviderPlan.provider_plan_id == subscription.provider_plan_id,
                )
                .first()
            )
            if provider_plan is not None:
                subscription.plan = provider_plan.plan
                subscription.billing_interval = provider_plan.billing_interval

        if period_end is None:
            period_end = _period_end(period_start, subscription.billing_interval)

        subscription.status = SubscriptionStatus.active
        subscription.current_period_start = period_start
        subscription.current_period_end = period_end
        subscription.cancel_at_period_end = False
        subscription.updated_at = datetime.utcnow()
        self.db.add(subscription)

        if provider_payment_id:
            existing_payment = (
                self.db.query(models.Payment)
                .filter(models.Payment.provider_payment_id == provider_payment_id)
                .first()
            )
            if existing_payment is None:
                amount = price_for(subscription.plan, subscription.billing_interval) or 0
                self.db.add(models.Payment(
                    agency_id=subscription.agency_id,
                    subscription_id=subscription.id,
                    provider="razorpay",
                    provider_payment_id=provider_payment_id,
                    provider_subscription_id=subscription.provider_subscription_id,
                    amount=amount,
                    currency="INR",
                    status=models.PaymentStatus.captured,
                    description=f"{subscription.plan.value} ({subscription.billing_interval.value})",
                ))
        self.db.commit()

    # ---- webhook ---------------------------------------------------------------

    def handle_webhook(self, raw_body: str, signature: str) -> dict:
        if not self.razorpay.verify_webhook_signature(raw_body, signature):
            raise InvalidPaymentSignatureError()

        body_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()
        event_row = self.db.query(models.WebhookEvent).filter(models.WebhookEvent.body_sha256 == body_hash).first()
        if event_row is not None and event_row.processed_at is not None:
            return {"status": "duplicate_ignored", "event": event_row.event_type}

        payload = json.loads(raw_body)
        event_type = payload.get("event", "unknown")

        if event_row is None:
            event_row = models.WebhookEvent(
                provider="razorpay", event_type=event_type, body_sha256=body_hash, payload=payload,
            )
            self.db.add(event_row)
            self.db.commit()

        entity_payload = payload.get("payload", {})
        subscription_entity = (entity_payload.get("subscription") or {}).get("entity")
        payment_entity = (entity_payload.get("payment") or {}).get("entity")

        if subscription_entity:
            self._apply_subscription_event(event_type, subscription_entity, payment_entity)
        elif payment_entity and event_type == "payment.failed":
            self._apply_payment_failed(payment_entity)

        event_row.processed_at = datetime.utcnow()
        self.db.add(event_row)
        self.db.commit()
        return {"status": "processed", "event": event_type}

    def _apply_subscription_event(self, event_type: str, subscription_entity: dict, payment_entity: dict | None) -> None:
        provider_subscription_id = subscription_entity.get("id")
        subscription = (
            self.db.query(models.Subscription)
            .filter(models.Subscription.provider_subscription_id == provider_subscription_id)
            .first()
        )
        if subscription is None:
            return  # an event for a subscription this deployment doesn't recognize - ignored, not an error

        if event_type in ("subscription.activated", "subscription.charged"):
            period_start = (
                datetime.utcfromtimestamp(subscription_entity["current_start"])
                if subscription_entity.get("current_start") else datetime.utcnow()
            )
            # None (not a stale-interval fallback) when Razorpay's payload
            # doesn't include current_end - _activate() resolves the real
            # interval from provider_plan_id first, then computes this
            # itself, so the fallback is never based on a pre-activation
            # (possibly still-old) subscription.billing_interval value.
            period_end = (
                datetime.utcfromtimestamp(subscription_entity["current_end"])
                if subscription_entity.get("current_end") else None
            )
            self._activate(
                subscription,
                provider_payment_id=payment_entity.get("id") if payment_entity else None,
                period_start=period_start, period_end=period_end,
            )
        elif event_type == "subscription.cancelled":
            subscription.status = SubscriptionStatus.cancelled
            subscription.cancelled_at = datetime.utcnow()
            self.db.add(subscription)
            self.db.commit()
        elif event_type in ("subscription.pending", "subscription.halted"):
            subscription.status = SubscriptionStatus.past_due
            self.db.add(subscription)
            self.db.commit()

    def _apply_payment_failed(self, payment_entity: dict) -> None:
        provider_subscription_id = payment_entity.get("subscription_id") or (payment_entity.get("notes") or {}).get("subscription_id")
        if not provider_subscription_id:
            return
        subscription = (
            self.db.query(models.Subscription)
            .filter(models.Subscription.provider_subscription_id == provider_subscription_id)
            .first()
        )
        if subscription is not None and subscription.status == SubscriptionStatus.active:
            subscription.status = SubscriptionStatus.past_due
            self.db.add(subscription)
            self.db.commit()

    # ---- upgrade / downgrade -----------------------------------------------

    def change_plan(self, agency: models.Agency, new_plan: SubscriptionPlan, new_interval: BillingInterval) -> dict:
        """ALWAYS requires a fresh, real checkout - a Razorpay Subscription
        being created, a plan being "selected", or an agency merely being
        on its free trial are never treated as proof of payment (a real
        billing-flow defect confirmed during Razorpay sandbox testing:
        this method used to apply a still-trialing agency's chosen plan/
        interval directly, for free, with no checkout at all - see git
        history for the incident). The only two real actions here are:
        (1) block the change if current usage wouldn't fit the new plan
        (EntitlementService.validate_plan_change - never silently
        deactivates resources to force a fit), and (2) if a real paid
        Razorpay subscription already exists, cancel it immediately so
        the agency is never charged twice for two plans at once. Every
        actual plan/entitlement change happens only inside _activate(),
        after start_checkout() + a verified payment - never here."""
        if new_plan == SubscriptionPlan.enterprise:
            raise CheckoutNotPossibleError("Enterprise plans are arranged directly with sales - contact us to change to this plan.")

        violations = self.entitlements.validate_plan_change(agency, new_plan)
        if violations:
            raise PlanChangeBlockedError(violations)

        subscription = self.get(agency)
        if (
            subscription is not None
            and subscription.status in (SubscriptionStatus.active, SubscriptionStatus.past_due)
            and subscription.provider_subscription_id
            and self.razorpay.is_configured
        ):
            try:
                self.razorpay.cancel_subscription(subscription.provider_subscription_id, at_cycle_end=False)
            except PaymentsNotConfiguredError:
                pass
        return {"requires_checkout": True, "plan": new_plan, "billing_interval": new_interval}

    # ---- cancellation ------------------------------------------------------

    def cancel(self, agency: models.Agency) -> models.Subscription:
        subscription = self.get(agency)
        if subscription is None:
            raise NoSubscriptionError("This agency has no subscription to cancel.")

        if subscription.provider_subscription_id and self.razorpay.is_configured:
            try:
                self.razorpay.cancel_subscription(subscription.provider_subscription_id, at_cycle_end=True)
            except PaymentsNotConfiguredError:
                pass

        subscription.cancel_at_period_end = True
        subscription.cancelled_at = datetime.utcnow()
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription
