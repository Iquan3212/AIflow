// Mirrors backend/app/schemas.py's billing schemas and
// backend/app/services/billing/plans.py's PLANS - the backend is always
// the source of truth for prices/limits/features; this file only shapes
// what the API already returns, it never hardcodes a number itself.

export type PlanId = "starter" | "growth" | "professional" | "enterprise";
export type BillingInterval = "monthly" | "annual";
export type SubscriptionStatus = "trialing" | "active" | "past_due" | "cancelled" | "expired";

export interface AnnualSavings {
    monthly_equivalent: number;
    annual_price: number;
    amount_saved: number;
    percent_saved: number;
}

export interface Plan {
    id: PlanId;
    name: string;
    tagline: string;
    price_monthly: number | null;
    price_annual: number | null;
    active_property_limit: number | null;
    user_limit: number | null;
    project_limit: number | null;
    ai_action_limit: number | null;
    features: string[];
    highlighted: boolean;
    annual_savings: AnnualSavings | null;
}

export interface UsageMetric {
    used: number;
    limit: number | null;
}

export interface UsageSummary {
    active_properties: UsageMetric;
    projects: UsageMetric;
    users: UsageMetric;
    ai_actions: UsageMetric;
}

export interface Subscription {
    plan: PlanId;
    billing_interval: BillingInterval;
    status: SubscriptionStatus;
    provider: string | null;
    current_period_start: string | null;
    current_period_end: string | null;
    trial_start: string | null;
    trial_end: string | null;
    cancel_at_period_end: boolean;
    cancelled_at: string | null;
    usage: UsageSummary;
}

export interface CheckoutResponse {
    provider_subscription_id: string;
    key_id: string;
    amount: number;
    currency: string;
    plan: PlanId;
    billing_interval: BillingInterval;
}

export interface ChangePlanResponse {
    requires_checkout: boolean;
    subscription: Subscription | null;
}

export interface Payment {
    id: string;
    amount: string;
    currency: string;
    status: "created" | "authorized" | "captured" | "failed" | "refunded";
    description: string | null;
    created_at: string;
}

// Human-readable labels for the feature keys PLANS.features returns -
// kept in sync with services/billing/plans.py's FEATURE_* constants by
// hand (a small, stable, rarely-changing vocabulary), not derived.
export const FEATURE_LABELS: Record<string, string> = {
    marketplace_listing: "Marketplace listing",
    inventory: "Project & property inventory",
    basic_crm: "Basic CRM",
    buyer_conversion: "Inquiries, site visits & bookings",
    knowledge_base: "Knowledge Base",
    advanced_knowledge_base: "Advanced Knowledge Base / RAG",
    customer_ai_assistant: "AI property assistant (customer-facing)",
    gmail_integration: "Gmail integration",
    basic_workflows: "Basic workflows",
    workflow_automation: "Workflow automation",
    ai_action_approvals: "AI action approvals",
    basic_analytics: "Basic analytics",
    advanced_analytics: "Advanced analytics",
    ai_workforce_specialists: "AI Workforce specialists (Lead Qual, Property Match, Sales, Site Visit, Customer Relations)",
    ai_manager: "AI Manager & multi-agent orchestration",
    advanced_approval_controls: "Advanced approval controls",
    custom_integrations: "Custom integrations",
    whatsapp_instagram_channels: "WhatsApp & Instagram channels",
    sso: "Single sign-on (SSO)",
};
