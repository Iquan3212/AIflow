"""
Agency subscription/payment endpoints.

  GET  /billing/plans                 public - the pricing page reads this
  GET  /billing/subscription           this agency's subscription + usage (any signed-in agency user)
  POST /billing/checkout               owner-only - create a Razorpay checkout
  POST /billing/checkout/confirm       owner-only - verify a completed checkout
  POST /billing/webhook                Razorpay only (signature-verified, no auth header)
  POST /billing/change-plan            owner-only - upgrade/downgrade
  POST /billing/cancel                 owner-only - cancel (effective at period end)
  GET  /billing/payments               this agency's payment history (any signed-in agency user)

Never trusts a plan id, price, or payment outcome the client claims -
every price comes from app.services.billing.plans; every activation
comes from a verified Razorpay signature or webhook (see
subscription_service.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency, require_billing_owner
from app.models import BillingInterval, SubscriptionPlan
from app.services.billing.entitlement_service import EntitlementService
from app.services.billing.plans import PLANS, annual_savings
from app.services.billing.razorpay_client import PaymentsNotConfiguredError
from app.services.billing.subscription_service import (
    CheckoutNotPossibleError,
    InvalidPaymentSignatureError,
    NoSubscriptionError,
    PlanChangeBlockedError,
    SubscriptionService,
)

router = APIRouter(prefix="/billing", tags=["billing"])


def _to_plan(value: str) -> SubscriptionPlan:
    try:
        return SubscriptionPlan(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown plan: {value!r}")


def _to_interval(value: str) -> BillingInterval:
    try:
        return BillingInterval(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown billing_interval: {value!r}")


def _subscription_out(db: Session, agency: models.Agency) -> schemas.SubscriptionOut:
    entitlements = EntitlementService(db)
    subscription = entitlements.get_subscription(agency)
    usage = entitlements.get_usage_summary(agency)
    if subscription is None:
        # A real Subscription always exists from signup onward (see
        # routers/auth.py) or the one-time migration backfill - this is
        # only reachable for a pre-billing agency that predates both,
        # which no longer exists in this deployment's data, but the API
        # still answers honestly rather than 500ing.
        raise HTTPException(status_code=404, detail="This agency has no subscription yet.")
    return schemas.SubscriptionOut(
        plan=subscription.plan.value,
        billing_interval=subscription.billing_interval.value,
        status=subscription.status.value,
        provider=subscription.provider,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_start=subscription.trial_start,
        trial_end=subscription.trial_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        cancelled_at=subscription.cancelled_at,
        usage=schemas.UsageSummaryOut(**usage),
    )


@router.get("/plans", response_model=list[schemas.PlanOut])
def list_plans():
    return [
        schemas.PlanOut(
            id=definition.id.value,
            name=definition.name,
            tagline=definition.tagline,
            price_monthly=definition.price_monthly,
            price_annual=definition.price_annual,
            active_property_limit=definition.active_property_limit,
            user_limit=definition.user_limit,
            project_limit=definition.project_limit,
            ai_action_limit=definition.ai_action_limit,
            features=list(definition.features),
            highlighted=definition.highlighted,
            annual_savings=annual_savings(definition.id),
        )
        for definition in PLANS.values()
    ]


@router.get("/subscription", response_model=schemas.SubscriptionOut)
def get_subscription(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return _subscription_out(db, agency)


@router.post("/checkout", response_model=schemas.CheckoutResponse)
def create_checkout(
    payload: schemas.CheckoutRequest,
    agency: models.Agency = Depends(require_billing_owner),
    db: Session = Depends(get_db),
):
    plan = _to_plan(payload.plan)
    interval = _to_interval(payload.billing_interval)
    try:
        return SubscriptionService(db).start_checkout(agency, plan, interval)
    except CheckoutNotPossibleError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PaymentsNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/checkout/confirm", response_model=schemas.SubscriptionOut)
def confirm_checkout(
    payload: schemas.ConfirmPaymentRequest,
    agency: models.Agency = Depends(require_billing_owner),
    db: Session = Depends(get_db),
):
    try:
        SubscriptionService(db).confirm_checkout(
            agency,
            razorpay_payment_id=payload.razorpay_payment_id,
            razorpay_subscription_id=payload.razorpay_subscription_id,
            razorpay_signature=payload.razorpay_signature,
        )
    except NoSubscriptionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidPaymentSignatureError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _subscription_out(db, agency)


@router.post("/webhook", status_code=200)
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """No auth header - Razorpay itself is the caller. The HMAC signature
    in X-Razorpay-Signature (verified against the raw, unparsed body) is
    the only thing that authenticates this request; a request with a
    missing/invalid signature is rejected before the body is even parsed
    as JSON."""
    raw_body = (await request.body()).decode("utf-8")
    signature = request.headers.get("x-razorpay-signature", "")
    try:
        result = SubscriptionService(db).handle_webhook(raw_body, signature)
    except InvalidPaymentSignatureError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    return result


@router.post("/change-plan", response_model=schemas.ChangePlanResponse)
def change_plan(
    payload: schemas.ChangePlanRequest,
    agency: models.Agency = Depends(require_billing_owner),
    db: Session = Depends(get_db),
):
    plan = _to_plan(payload.plan)
    interval = _to_interval(payload.billing_interval)
    try:
        result = SubscriptionService(db).change_plan(agency, plan, interval)
    except CheckoutNotPossibleError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PlanChangeBlockedError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "violations": exc.violations})

    if result["requires_checkout"]:
        return schemas.ChangePlanResponse(requires_checkout=True, subscription=None)
    return schemas.ChangePlanResponse(requires_checkout=False, subscription=_subscription_out(db, agency))


@router.post("/cancel", response_model=schemas.SubscriptionOut)
def cancel_subscription(
    agency: models.Agency = Depends(require_billing_owner),
    db: Session = Depends(get_db),
):
    try:
        SubscriptionService(db).cancel(agency)
    except NoSubscriptionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _subscription_out(db, agency)


@router.get("/payments", response_model=list[schemas.PaymentOut])
def list_payments(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Payment)
        .filter(models.Payment.agency_id == agency.id)
        .order_by(models.Payment.created_at.desc())
        .all()
    )
