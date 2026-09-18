import api from "./api";
import type {
    ChangePlanResponse, CheckoutResponse, Payment, Plan, Subscription,
} from "../types/billing";

export async function listPlans(): Promise<Plan[]> {
    const response = await api.get<Plan[]>("/billing/plans");
    return response.data;
}

export async function getSubscription(): Promise<Subscription> {
    const response = await api.get<Subscription>("/billing/subscription");
    return response.data;
}

export async function createCheckout(plan: string, billingInterval: string): Promise<CheckoutResponse> {
    const response = await api.post<CheckoutResponse>("/billing/checkout", { plan, billing_interval: billingInterval });
    return response.data;
}

export async function confirmCheckout(payload: {
    razorpay_payment_id: string;
    razorpay_subscription_id: string;
    razorpay_signature: string;
}): Promise<Subscription> {
    const response = await api.post<Subscription>("/billing/checkout/confirm", payload);
    return response.data;
}

export async function changePlan(plan: string, billingInterval: string): Promise<ChangePlanResponse> {
    const response = await api.post<ChangePlanResponse>("/billing/change-plan", { plan, billing_interval: billingInterval });
    return response.data;
}

export async function cancelSubscription(): Promise<Subscription> {
    const response = await api.post<Subscription>("/billing/cancel");
    return response.data;
}

export async function listPayments(): Promise<Payment[]> {
    const response = await api.get<Payment[]>("/billing/payments");
    return response.data;
}
