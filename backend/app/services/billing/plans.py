"""
Single source of truth for AIFlow's Agency subscription plans - prices,
limits, and feature keys. Nothing else in the app hardcodes a price or a
limit number; every entitlement check and every pricing/billing API
response reads from PLANS below.

Prices are locked launch values (paise stored as INR rupees, whole
number - Razorpay's own API wants amounts in the smallest currency unit
(paise) and RazorpayClient converts at the API boundary, so this module
stays in human-readable rupees throughout).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import BillingInterval, SubscriptionPlan


@dataclass(frozen=True)
class PlanDefinition:
    id: SubscriptionPlan
    name: str
    tagline: str
    price_monthly: int | None  # rupees; None = custom/Contact Sales (Enterprise)
    price_annual: int | None
    active_property_limit: int | None  # None = unlimited
    user_limit: int | None
    project_limit: int | None
    ai_action_limit: int | None
    features: tuple[str, ...] = field(default_factory=tuple)
    highlighted: bool = False


# Feature keys - each maps to a real, already-implemented product
# capability (see the Monetization report for the audit trail). Nothing
# here names a feature that doesn't exist in the app today.
FEATURE_MARKETPLACE_LISTING = "marketplace_listing"
FEATURE_INVENTORY = "inventory"
FEATURE_BASIC_CRM = "basic_crm"
FEATURE_BUYER_CONVERSION = "buyer_conversion"  # inquiries/site visits/bookings/saved properties
FEATURE_KNOWLEDGE_BASE = "knowledge_base"
FEATURE_ADVANCED_KNOWLEDGE_BASE = "advanced_knowledge_base"
FEATURE_CUSTOMER_AI_ASSISTANT = "customer_ai_assistant"  # widget/marketplace conversation AI
FEATURE_GMAIL = "gmail_integration"
FEATURE_BASIC_WORKFLOWS = "basic_workflows"
FEATURE_WORKFLOW_AUTOMATION = "workflow_automation"
FEATURE_AI_ACTION_APPROVALS = "ai_action_approvals"
FEATURE_BASIC_ANALYTICS = "basic_analytics"
FEATURE_ADVANCED_ANALYTICS = "advanced_analytics"
FEATURE_AI_WORKFORCE_SPECIALISTS = "ai_workforce_specialists"  # Lead Qual/Property Match/Sales/Site Visit/Customer Relations
FEATURE_AI_MANAGER = "ai_manager"  # Manager + multi-agent orchestration
FEATURE_ADVANCED_APPROVAL_CONTROLS = "advanced_approval_controls"
FEATURE_CUSTOM_INTEGRATIONS = "custom_integrations"
FEATURE_WHATSAPP_INSTAGRAM = "whatsapp_instagram_channels"
FEATURE_SSO = "sso"

_STARTER_FEATURES = (
    FEATURE_MARKETPLACE_LISTING,
    FEATURE_INVENTORY,
    FEATURE_BASIC_CRM,
    FEATURE_BUYER_CONVERSION,
    FEATURE_KNOWLEDGE_BASE,
    FEATURE_CUSTOMER_AI_ASSISTANT,
    FEATURE_GMAIL,
    FEATURE_BASIC_WORKFLOWS,
    FEATURE_BASIC_ANALYTICS,
)

_GROWTH_FEATURES = _STARTER_FEATURES + (
    FEATURE_AI_WORKFORCE_SPECIALISTS,
    FEATURE_ADVANCED_KNOWLEDGE_BASE,
    FEATURE_WORKFLOW_AUTOMATION,
    FEATURE_AI_ACTION_APPROVALS,
    FEATURE_ADVANCED_ANALYTICS,
    FEATURE_WHATSAPP_INSTAGRAM,
)

_PROFESSIONAL_FEATURES = _GROWTH_FEATURES + (
    FEATURE_AI_MANAGER,
    FEATURE_ADVANCED_APPROVAL_CONTROLS,
    FEATURE_CUSTOM_INTEGRATIONS,
)

_ENTERPRISE_FEATURES = _PROFESSIONAL_FEATURES + (FEATURE_SSO,)

PLANS: dict[SubscriptionPlan, PlanDefinition] = {
    SubscriptionPlan.starter: PlanDefinition(
        id=SubscriptionPlan.starter,
        name="Starter",
        tagline="For small agencies getting organized.",
        price_monthly=4_199,
        price_annual=41_986,
        active_property_limit=25,
        user_limit=3,
        project_limit=3,
        ai_action_limit=300,
        features=_STARTER_FEATURES,
    ),
    SubscriptionPlan.growth: PlanDefinition(
        id=SubscriptionPlan.growth,
        name="Growth",
        tagline="For agencies ready to automate sales with AI.",
        price_monthly=10_499,
        price_annual=104_986,
        active_property_limit=100,
        user_limit=10,
        project_limit=15,
        ai_action_limit=1_500,
        features=_GROWTH_FEATURES,
        highlighted=True,
    ),
    SubscriptionPlan.professional: PlanDefinition(
        id=SubscriptionPlan.professional,
        name="Professional",
        tagline="For established teams running an AI-powered sales operation.",
        price_monthly=20_999,
        price_annual=209_986,
        active_property_limit=300,
        user_limit=25,
        project_limit=None,
        ai_action_limit=5_000,
        features=_PROFESSIONAL_FEATURES,
    ),
    SubscriptionPlan.enterprise: PlanDefinition(
        id=SubscriptionPlan.enterprise,
        name="Enterprise",
        tagline="For large real-estate organizations that need custom limits, integrations, and support.",
        price_monthly=None,
        price_annual=None,
        active_property_limit=None,
        user_limit=None,
        project_limit=None,
        ai_action_limit=None,
        features=_ENTERPRISE_FEATURES,
    ),
}

TRIAL_DAYS = 14


def get_plan(plan: SubscriptionPlan) -> PlanDefinition:
    return PLANS[plan]


def price_for(plan: SubscriptionPlan, interval: BillingInterval) -> int | None:
    definition = PLANS[plan]
    return definition.price_monthly if interval == BillingInterval.monthly else definition.price_annual


def annual_savings(plan: SubscriptionPlan) -> dict | None:
    """Real, computed savings (never a hardcoded/guessed percentage) -
    None for a plan with no public price (Enterprise)."""
    definition = PLANS[plan]
    if definition.price_monthly is None or definition.price_annual is None:
        return None
    monthly_equivalent = definition.price_monthly * 12
    saved = monthly_equivalent - definition.price_annual
    percent = round((saved / monthly_equivalent) * 100, 1) if monthly_equivalent else 0.0
    return {"monthly_equivalent": monthly_equivalent, "annual_price": definition.price_annual, "amount_saved": saved, "percent_saved": percent}
