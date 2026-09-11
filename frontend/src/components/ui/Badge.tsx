import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info" | "brand" | "flare";

const TONE_CLASSES: Record<BadgeTone, string> = {
    neutral: "bg-slate-100 text-slate-700",
    success: "bg-emerald-50 text-emerald-700",
    warning: "bg-amber-50 text-amber-700",
    danger: "bg-red-50 text-red-700",
    info: "bg-sky-50 text-sky-700",
    brand: "bg-brand-50 text-brand-700",
    flare: "bg-flare-50 text-flare-600",
};

export default function Badge({
    tone = "neutral",
    children,
    className = "",
}: {
    tone?: BadgeTone;
    children: ReactNode;
    className?: string;
}) {
    return (
        <span
            className={`inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]} ${className}`}
        >
            {children}
        </span>
    );
}
