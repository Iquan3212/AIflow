import { Fragment, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, Check, X } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getCurrentAgency } from "../../services/agency";
import {
    changePlan, confirmCheckout, createCheckout, getSubscription, listPlans,
} from "../../services/billing";
import { openRazorpaySubscriptionCheckout } from "../../utils/razorpayCheckout";
import { FEATURE_LABELS } from "../../types/billing";
import type { BillingInterval, Plan, Subscription } from "../../types/billing";

function formatRupees(amount: number): string {
    return `₹${amount.toLocaleString("en-IN")}`;
}

// The comparison matrix's row order/grouping - every feature key here
// must exist in at least one plan's `features` list (see
// services/billing/plans.py); a feature not yet implemented simply
// never appears in any plan and so never appears here either.
const COMPARISON_SECTIONS: { category: string; features: string[] }[] = [
    { category: "Inventory", features: ["inventory"] },
    { category: "CRM", features: ["basic_crm"] },
    { category: "Marketplace", features: ["marketplace_listing", "buyer_conversion"] },
    { category: "AI Workforce", features: ["customer_ai_assistant", "ai_workforce_specialists", "ai_manager"] },
    { category: "Automation", features: ["basic_workflows", "workflow_automation", "ai_action_approvals"] },
    { category: "Knowledge Base", features: ["knowledge_base", "advanced_knowledge_base"] },
    { category: "Channels", features: ["whatsapp_instagram_channels"] },
    { category: "Analytics", features: ["basic_analytics", "advanced_analytics"] },
    { category: "Support", features: ["gmail_integration", "custom_integrations", "sso"] },
];

export default function Pricing() {
    const navigate = useNavigate();
    const [interval, setInterval] = useState<BillingInterval>("monthly");
    const [plans, setPlans] = useState<Plan[] | null>(null);
    const [subscription, setSubscription] = useState<Subscription | null>(null);
    const [agencyEmail, setAgencyEmail] = useState<string | undefined>(undefined);
    const [error, setError] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [pendingPlan, setPendingPlan] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            const [planList, sub, agency] = await Promise.all([listPlans(), getSubscription(), getCurrentAgency()]);
            setPlans(planList);
            setSubscription(sub);
            setAgencyEmail(agency.contact_email);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    async function handleSelectPlan(plan: Plan) {
        setActionError(null);
        if (plan.id === "enterprise") {
            window.location.assign("mailto:sales@aiflow.example?subject=AIFlow%20Enterprise%20plan");
            return;
        }
        setPendingPlan(plan.id);
        try {
            const changeResult = await changePlan(plan.id, interval);
            if (!changeResult.requires_checkout) {
                // Still trialing, no payment method on file yet - the plan
                // switch is immediate and free; nothing to check out.
                await load();
                navigate("/billing?updated=1");
                return;
            }
            const checkout = await createCheckout(plan.id, interval);
            const result = await openRazorpaySubscriptionCheckout({
                keyId: checkout.key_id,
                providerSubscriptionId: checkout.provider_subscription_id,
                name: "AIFlow",
                description: `AIFlow ${plan.name} (${interval})`,
                prefillEmail: agencyEmail,
            });
            await confirmCheckout({
                razorpay_payment_id: result.razorpay_payment_id,
                razorpay_subscription_id: result.razorpay_subscription_id,
                razorpay_signature: result.razorpay_signature,
            });
            navigate("/billing?checkout=success");
        } catch (err) {
            if (err instanceof Error && err.message === "cancelled") {
                setActionError("Checkout was cancelled - no payment was made.");
            } else {
                setActionError(getErrorMessage(err));
            }
        } finally {
            setPendingPlan(null);
        }
    }

    if (error) {
        return (
            <AppShell>
                <ErrorState message={error} onRetry={load} />
            </AppShell>
        );
    }

    if (!plans || !subscription) {
        return (
            <AppShell>
                <LoadingState label="Loading plans…" />
            </AppShell>
        );
    }

    return (
        <AppShell>
            <PageHeader
                eyebrow="Plans"
                title="Choose the plan that fits your real-estate business"
                description="Run your inventory, CRM, AI workforce and sales operations in one place."
            />

            <div className="flex justify-center mb-9">
                <div className="inline-flex items-center bg-white border border-slate-200 rounded-xl p-1">
                    <button
                        onClick={() => setInterval("monthly")}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                            interval === "monthly" ? "bg-ink-950 text-white" : "text-slate-600"
                        }`}
                    >
                        Monthly
                    </button>
                    <button
                        onClick={() => setInterval("annual")}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors flex items-center gap-1.5 ${
                            interval === "annual" ? "bg-ink-950 text-white" : "text-slate-600"
                        }`}
                    >
                        Annual
                        <span className="text-[10px] font-bold bg-flare-500 text-ink-950 rounded-full px-1.5 py-0.5">SAVE</span>
                    </button>
                </div>
            </div>

            {actionError && (
                <div className="max-w-2xl mx-auto bg-red-50 border border-red-200 text-red-700 rounded-xl p-3.5 text-sm mb-6 text-center">
                    {actionError}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-14">
                {plans.map((plan) => {
                    const price = interval === "monthly" ? plan.price_monthly : plan.price_annual;
                    const isCurrent = subscription.plan === plan.id;
                    return (
                        <Card
                            key={plan.id}
                            className={`p-6 flex flex-col ${plan.highlighted ? "border-brand-600 border-2 shadow-glow relative" : ""}`}
                        >
                            {plan.highlighted && (
                                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-brand-600 text-white text-[11px] font-bold uppercase tracking-wide rounded-full px-3 py-1">
                                    Most popular
                                </span>
                            )}
                            <h2 className="font-display text-xl font-semibold text-ink-950">{plan.name}</h2>
                            <p className="text-xs text-slate-500 mt-1.5 min-h-[2.2rem]">{plan.tagline}</p>

                            <div className="mt-4 mb-1">
                                {price !== null ? (
                                    <>
                                        <span className="text-3xl font-semibold text-ink-950 font-mono-data">{formatRupees(price)}</span>
                                        <span className="text-sm text-slate-400">/{interval === "monthly" ? "month" : "year"}</span>
                                    </>
                                ) : (
                                    <span className="text-3xl font-semibold text-ink-950">Custom</span>
                                )}
                            </div>
                            {interval === "annual" && plan.annual_savings && (
                                <p className="text-xs text-emerald-700 font-medium mb-4">
                                    Save {formatRupees(plan.annual_savings.amount_saved)} ({plan.annual_savings.percent_saved}%) vs. monthly
                                </p>
                            )}
                            {(interval === "monthly" || !plan.annual_savings) && <div className="mb-4" />}

                            <ul className="text-sm text-slate-600 space-y-2 mb-5">
                                <li>
                                    <strong className="text-ink-950">{plan.active_property_limit ?? "Unlimited"}</strong> active property slots
                                </li>
                                <li>
                                    <strong className="text-ink-950">{plan.user_limit ?? "Unlimited"}</strong> team members
                                </li>
                                <li>
                                    <strong className="text-ink-950">{plan.ai_action_limit ?? "Custom"}</strong> AI actions/month
                                </li>
                            </ul>

                            <div className="flex-1" />

                            {isCurrent ? (
                                <Badge tone="brand" className="justify-center py-2">Current plan</Badge>
                            ) : (
                                <Button
                                    variant={plan.highlighted ? "primary" : "secondary"}
                                    className="w-full"
                                    loading={pendingPlan === plan.id}
                                    onClick={() => handleSelectPlan(plan)}
                                >
                                    {plan.id === "enterprise" ? "Contact Sales" : "Start Free Trial"}
                                </Button>
                            )}
                        </Card>
                    );
                })}
            </div>

            <h2 className="font-display text-2xl font-medium text-ink-950 mb-6 text-center">Compare plans</h2>
            <div className="overflow-x-auto -mx-4 sm:mx-0 mb-10">
                <table className="w-full min-w-[720px] border-separate border-spacing-0">
                    <thead>
                        <tr>
                            <th className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wide pb-3 pl-4 sm:pl-0 w-40" />
                            {plans.map((plan) => (
                                <th key={plan.id} className="text-center pb-3 px-3">
                                    <span className="text-sm font-semibold text-ink-950">{plan.name}</span>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {COMPARISON_SECTIONS.map((section) => (
                            <Fragment key={section.category}>
                                <tr>
                                    <td colSpan={plans.length + 1} className="pt-6 pb-2 pl-4 sm:pl-0 text-xs font-bold uppercase tracking-wide text-slate-400">
                                        {section.category}
                                    </td>
                                </tr>
                                {section.features.map((featureKey) => (
                                    <tr key={featureKey}>
                                        <td className="text-sm text-slate-600 py-2.5 pl-4 sm:pl-0 border-t border-slate-100">
                                            {FEATURE_LABELS[featureKey] ?? featureKey}
                                        </td>
                                        {plans.map((plan) => (
                                            <td key={plan.id} className="text-center py-2.5 px-3 border-t border-slate-100">
                                                {plan.features.includes(featureKey) ? (
                                                    <Check size={16} className="text-emerald-600 inline" aria-label="Included" />
                                                ) : (
                                                    <X size={14} className="text-slate-300 inline" aria-label="Not included" />
                                                )}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </Fragment>
                        ))}
                    </tbody>
                </table>
            </div>

            <Card className="p-7 bg-ink-950 border-ink-900 max-w-2xl mx-auto flex items-center gap-4">
                <div className="w-11 h-11 rounded-xl bg-flare-500/15 text-flare-400 flex items-center justify-center shrink-0">
                    <Bot size={20} aria-hidden="true" />
                </div>
                <div>
                    <p className="text-white font-display font-medium">Need something bigger?</p>
                    <p className="text-slate-300 text-sm mt-0.5">
                        Enterprise plans include custom limits, SSO, dedicated onboarding and support - contact sales for pricing.
                    </p>
                </div>
            </Card>
        </AppShell>
    );
}
