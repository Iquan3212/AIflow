// Loads and drives Razorpay's own hosted Checkout widget - AIFlow never
// collects a card number or bank detail itself; this is the one and
// only place card data is entered, directly into Razorpay's iframe.

declare global {
    interface Window {
        Razorpay: new (options: Record<string, unknown>) => { open: () => void };
    }
}

let scriptPromise: Promise<void> | null = null;

export function loadRazorpayScript(): Promise<void> {
    if (window.Razorpay) return Promise.resolve();
    if (scriptPromise) return scriptPromise;
    scriptPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://checkout.razorpay.com/v1/checkout.js";
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("Couldn't load the payment widget. Check your connection and try again."));
        document.body.appendChild(script);
    });
    return scriptPromise;
}

export interface RazorpaySuccess {
    razorpay_payment_id: string;
    razorpay_subscription_id: string;
    razorpay_signature: string;
}

/** Opens Razorpay's hosted checkout for a subscription. Resolves with
 * the (unverified - the backend verifies the signature before trusting
 * any of this) payment/subscription/signature triple on success; rejects
 * if the customer dismisses the widget (cancelled checkout) or Razorpay
 * itself reports a payment failure. */
export async function openRazorpaySubscriptionCheckout(options: {
    keyId: string;
    providerSubscriptionId: string;
    name: string;
    description: string;
    prefillEmail?: string;
}): Promise<RazorpaySuccess> {
    await loadRazorpayScript();

    return new Promise((resolve, reject) => {
        const razorpay = new window.Razorpay({
            key: options.keyId,
            subscription_id: options.providerSubscriptionId,
            name: "AIFlow",
            description: options.description,
            prefill: options.prefillEmail ? { email: options.prefillEmail } : undefined,
            theme: { color: "#2A5240" },
            handler: (response: RazorpaySuccess) => resolve(response),
            modal: {
                ondismiss: () => reject(new Error("cancelled")),
            },
        });
        razorpay.open();
    });
}
