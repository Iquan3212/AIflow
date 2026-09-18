import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, CreditCard } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import type { BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { cancelSubscription, getSubscription, listPayments, listPlans } from "../../services/billing";
import type { Payment, Plan, Subscription, UsageMetric } from "../../types/billing";

function formatRupees(amount: number): string {
    return `₹${amount.toLocaleString("en-IN")}`;
}

const STATUS_TONE: Record<Subscription["status"], BadgeTone> = {
    trialing: "info",
    active: "success",
    past_due: "warning",
    cancelled: "danger",
    expired: "danger",
};

const STATUS_LABEL: Record<Subscription["status"], string> = {
    trialing: "Trial",
    active: "Active",
    past_due: "Payment past due",
    cancelled: "Cancelled",
    expired: "Expired",
};

function UsageBar({ label, metric }: { label: string; metric: UsageMetric }) {
    const pct = metric.limit ? Math.min(100, Math.round((metric.used / metric.limit) * 100)) : 0;
    let message: string | null = null;
    let barTone = "bg-brand-600";
    if (metric.limit !== null) {
        if (pct >= 100) {
            message = `${label} limit reached.`;
            barTone = "bg-red-500";
        } else if (pct >= 95) {
            message = `Only ${metric.limit - metric.used} ${label.toLowerCase()} slot(s) remain.`;
            barTone = "bg-amber-500";
        } else if (pct >= 80) {
            message = `You're approaching your ${label.toLowerCase()} limit.`;
            barTone = "bg-amber-500";
        }
    }
    return (
        <div>
            <div className="flex items-center justify-between text-sm mb-1.5">
                <span className="font-medium text-ink-950">{label}</span>
                <span className="font-mono-data text-slate-500">
                    {metric.used} / {metric.limit ?? "Unlimited"}
                </span>
            </div>
            {metric.limit !== null && (
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div className={`h-full ${barTone} transition-all`} style={{ width: `${pct}%` }} />
                </div>
            )}
            {message && <p className="text-xs text-amber-700 mt-1">{message}</p>}
        </div>
    );
}

export default function Billing() {
    const [params] = useSearchParams();
    const [subscription, setSubscription] = useState<Subscription | null>(null);
    const [plans, setPlans] = useState<Plan[] | null>(null);
    const [payments, setPayments] = useState<Payment[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [cancelling, setCancelling] = useState(false);
    const [showSuccessBanner, setShowSuccessBanner] = useState(params.get("checkout") === "success");

    async function load() {
        setError(null);
        try {
            const [sub, planList, paymentList] = await Promise.all([getSubscription(), listPlans(), listPayments()]);
            setSubscription(sub);
            setPlans(planList);
            setPayments(paymentList);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    async function handleCancel() {
        if (!confirm("Cancel your AIFlow subscription? You'll keep access until the end of your current billing period.")) return;
        setCancelling(true);
        try {
            const updated = await cancelSubscription();
            setSubscription(updated);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setCancelling(false);
        }
    }

    if (error) {
        return (
            <AppShell>
                <ErrorState message={error} onRetry={load} />
            </AppShell>
        );
    }

    if (!subscription || !plans) {
        return (
            <AppShell>
                <LoadingState label="Loading billing…" />
            </AppShell>
        );
    }

    const plan = plans.find((p) => p.id === subscription.plan);
    const price = plan
        ? (subscription.billing_interval === "monthly" ? plan.price_monthly : plan.price_annual)
        : null;
    const renewalDate = subscription.current_period_end
        ? new Date(subscription.current_period_end).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
        : null;

    return (
        <AppShell>
            <PageHeader
                eyebrow="Billing"
                title="Subscription"
                description="Your plan, usage, and payment history."
                actions={<Link to="/pricing"><Button variant="secondary">Change plan</Button></Link>}
            />

            {showSuccessBanner && (
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl p-4 mb-6 flex items-center gap-3">
                    <CheckCircle2 size={18} className="shrink-0" />
                    <p className="text-sm font-medium flex-1">Your AIFlow subscription is active.</p>
                    <button onClick={() => setShowSuccessBanner(false)} className="text-emerald-700 text-xs font-semibold">Dismiss</button>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-6 mb-8">
                <Card className="p-6">
                    <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
                        <div>
                            <p className="text-xs text-slate-400 uppercase tracking-wide font-semibold mb-1">Current plan</p>
                            <p className="font-display text-2xl font-medium text-ink-950">{plan?.name ?? subscription.plan}</p>
                            {price !== null && (
                                <p className="text-sm text-slate-500 mt-0.5">
                                    {formatRupees(price)}/{subscription.billing_interval === "monthly" ? "month" : "year"}
                                </p>
                            )}
                        </div>
                        <Badge tone={STATUS_TONE[subscription.status]}>{STATUS_LABEL[subscription.status]}</Badge>
                    </div>

                    {subscription.status === "trialing" && subscription.trial_end && (
                        <p className="text-sm text-brand-700 bg-brand-50 rounded-lg p-3 mb-5">
                            Your free trial ends {new Date(subscription.trial_end).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}.
                        </p>
                    )}
                    {subscription.cancel_at_period_end && (
                        <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3 mb-5">
                            Your subscription is set to cancel at the end of the current period{renewalDate ? ` (${renewalDate})` : ""}.
                        </p>
                    )}

                    <div className="space-y-5">
                        <UsageBar label="Active properties" metric={subscription.usage.active_properties} />
                        <UsageBar label="Projects" metric={subscription.usage.projects} />
                        <UsageBar label="Team members" metric={subscription.usage.users} />
                        <UsageBar label="AI actions" metric={subscription.usage.ai_actions} />
                    </div>

                    {renewalDate && !subscription.cancel_at_period_end && (
                        <p className="text-xs text-slate-400 mt-5">Renews {renewalDate}.</p>
                    )}

                    <div className="flex items-center gap-3 mt-6 pt-5 border-t border-slate-100">
                        <Link to="/pricing"><Button variant="secondary">Manage subscription</Button></Link>
                        {!subscription.cancel_at_period_end && subscription.status !== "cancelled" && (
                            <Button variant="ghost" className="!text-red-600 hover:!bg-red-50" loading={cancelling} onClick={handleCancel}>
                                Cancel subscription
                            </Button>
                        )}
                    </div>
                </Card>

                <Card className="p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <CreditCard size={16} className="text-slate-400" aria-hidden="true" />
                        <h2 className="text-sm font-semibold text-slate-700">Payment history</h2>
                    </div>
                    {payments === null && <LoadingState label="Loading payments…" />}
                    {payments && payments.length === 0 && (
                        <EmptyState title="No payments yet" description="Your payment history will appear here once your first charge succeeds." />
                    )}
                    {payments && payments.length > 0 && (
                        <ul className="divide-y divide-slate-100">
                            {payments.map((payment) => (
                                <li key={payment.id} className="py-3 flex items-center justify-between gap-3">
                                    <div className="min-w-0">
                                        <p className="text-sm font-medium text-ink-950">{formatRupees(Number(payment.amount))}</p>
                                        <p className="text-xs text-slate-400">{new Date(payment.created_at).toLocaleDateString()}</p>
                                    </div>
                                    <Badge tone={payment.status === "captured" ? "success" : payment.status === "failed" ? "danger" : "neutral"}>
                                        {payment.status}
                                    </Badge>
                                </li>
                            ))}
                        </ul>
                    )}
                </Card>
            </div>
        </AppShell>
    );
}
