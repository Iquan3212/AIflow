import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "dark" | "flare";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: Variant;
    size?: Size;
    loading?: boolean;
}

const VARIANT_CLASSES: Record<Variant, string> = {
    primary:
        "bg-brand-600 text-white shadow-glow hover:bg-brand-700 active:bg-brand-800 disabled:bg-brand-300 disabled:shadow-none",
    secondary:
        "bg-white text-ink-900 border border-slate-200 hover:border-ink-900 disabled:text-slate-400 disabled:border-slate-200",
    ghost:
        "bg-transparent text-slate-600 hover:bg-slate-100 disabled:text-slate-300",
    danger:
        "bg-red-600 text-white shadow-soft hover:bg-red-700 disabled:bg-red-300",
    dark:
        "bg-ink-900 text-white shadow-soft hover:bg-ink-800 disabled:bg-slate-500",
    flare:
        "bg-flare-500 text-ink-950 shadow-flare hover:bg-flare-600 disabled:bg-flare-300",
};

const SIZE_CLASSES: Record<Size, string> = {
    sm: "text-sm px-4 py-1.5 gap-1.5",
    md: "text-sm px-5 py-2.5 gap-2",
    lg: "text-base px-7 py-3.5 gap-2.5",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ variant = "primary", size = "md", loading, disabled, className = "", children, ...props }, ref) => {
        return (
            <button
                ref={ref}
                disabled={disabled || loading}
                className={`inline-flex items-center justify-center rounded-full font-semibold tracking-tight transition-all duration-200
                    focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500
                    disabled:cursor-not-allowed active:scale-[0.98]
                    ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
                {...props}
            >
                {loading && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                {children}
            </button>
        );
    }
);
Button.displayName = "Button";

export default Button;
