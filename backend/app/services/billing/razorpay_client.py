"""
Thin wrapper over the official `razorpay` Python SDK (v2.0.1, the
current server-side integration Razorpay documents: Plans + Subscriptions
API for recurring billing, HMAC-SHA256 signature verification for both
checkout confirmation and webhooks). Nothing here talks to Razorpay
directly except through this module - callers never import `razorpay`
themselves.

No real Razorpay account exists for this repository. Every method that
needs one raises PaymentsNotConfiguredError until an operator sets
RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET/RAZORPAY_WEBHOOK_SECRET from a real
(test or live) Razorpay dashboard - the same "repo-side complete, blocked
on external credentials" shape this app already uses for Gmail/WhatsApp.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache

import razorpay
from razorpay.errors import SignatureVerificationError

from app.config import get_settings
from app.models import BillingInterval, SubscriptionPlan


class PaymentsNotConfiguredError(RuntimeError):
    def __init__(self):
        super().__init__(
            "Payments are not configured for this deployment yet - "
            "RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET are not set."
        )


class RazorpayClient:
    def __init__(self):
        settings = get_settings()
        self._key_id = settings.razorpay_key_id
        self._key_secret = settings.razorpay_key_secret
        self._webhook_secret = settings.razorpay_webhook_secret
        self._client = (
            razorpay.Client(auth=(self._key_id, self._key_secret))
            if self._key_id and self._key_secret
            else None
        )

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    @property
    def key_id(self) -> str:
        """Safe to expose to the frontend - Razorpay Checkout needs the
        public key id (never the secret) to open its own hosted widget."""
        return self._key_id

    def _client_or_raise(self) -> razorpay.Client:
        if self._client is None:
            raise PaymentsNotConfiguredError()
        return self._client

    # ---- Plans (one Razorpay Plan object per (our plan, interval) pair,
    # created lazily - see ProviderPlan/subscription_service.py) -----------

    def create_plan(self, *, plan: SubscriptionPlan, interval: BillingInterval, amount_rupees: int) -> str:
        client = self._client_or_raise()
        period = "monthly" if interval == BillingInterval.monthly else "yearly"
        result = client.plan.create({
            "period": period,
            "interval": 1,
            "item": {
                "name": f"AIFlow {plan.value.capitalize()} ({interval.value})",
                "amount": amount_rupees * 100,  # Razorpay wants paise
                "currency": "INR",
            },
        })
        return result["id"]

    # ---- Customers ---------------------------------------------------------

    def create_customer(self, *, name: str, email: str) -> str:
        client = self._client_or_raise()
        result = client.customer.create({"name": name, "email": email, "fail_existing": "0"})
        return result["id"]

    # ---- Subscriptions -------------------------------------------------------

    def create_subscription(
        self,
        *,
        provider_plan_id: str,
        customer_id: str | None,
        total_count: int,
        start_at: datetime | None = None,
    ) -> dict:
        """`start_at` (a real Razorpay Subscriptions feature) delays the
        first charge to the trial's end - the trial itself is tracked and
        enforced by AIFlow's own Subscription row regardless of whether
        Razorpay's own delayed-start matches it exactly."""
        client = self._client_or_raise()
        payload: dict = {
            "plan_id": provider_plan_id,
            "total_count": total_count,
            "customer_notify": 1,
        }
        if customer_id:
            payload["customer_id"] = customer_id
        if start_at:
            payload["start_at"] = int(start_at.timestamp())
        return client.subscription.create(payload)

    def fetch_subscription(self, provider_subscription_id: str) -> dict:
        return self._client_or_raise().subscription.fetch(provider_subscription_id)

    def cancel_subscription(self, provider_subscription_id: str, *, at_cycle_end: bool = True) -> dict:
        client = self._client_or_raise()
        return client.subscription.cancel(provider_subscription_id, {"cancel_at_cycle_end": 1 if at_cycle_end else 0})

    # ---- Signature verification - never trusts a bare frontend claim ------

    def verify_subscription_payment_signature(
        self, *, razorpay_payment_id: str, razorpay_subscription_id: str, razorpay_signature: str,
    ) -> bool:
        if not self._key_secret:
            return False
        try:
            razorpay.Utility().verify_subscription_payment_signature({
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_subscription_id": razorpay_subscription_id,
                "razorpay_signature": razorpay_signature,
                "secret": self._key_secret,
            })
            return True
        except SignatureVerificationError:
            return False

    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        if not self._webhook_secret:
            return False
        try:
            razorpay.Utility().verify_webhook_signature(body, signature, self._webhook_secret)
            return True
        except SignatureVerificationError:
            return False


@lru_cache
def get_razorpay_client() -> RazorpayClient:
    return RazorpayClient()
