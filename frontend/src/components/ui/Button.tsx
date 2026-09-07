import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "dark";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: Variant;
    size?: Size;
    loading?: boolean;
}

const VARIANT_CLASSES: Record<Variant, string> = {
    primary:
        "bg-brand-600 text-white shadow-soft hover:bg-brand-700 active:bg-brand-800 disabled:bg-brand-300",
    secondary:
        "bg-white text-slate-700 border border-slate-200 shadow-soft hover:border-slate-300 hover:bg-slate-50 disabled:text-slate-400",
    ghost:
        "bg-transparent text-slate-600 hover:bg-slate-100 disabled:text-slate-300",
    danger:
        "bg-red-600 text-white shadow-soft hover:bg-red-700 disabled:bg-red-300",
    dark:
        "bg-ink-900 text-white shadow-soft hover:bg-ink-800 disabled:bg-slate-500",
};

const SIZE_CLASSES: Record<Size, string> = {
    sm: "text-sm px-3 py-1.5 gap-1.5 rounded-lg",
    md: "text-sm px-4 py-2.5 gap-2 rounded-lg",
    lg: "text-base px-6 py-3.5 gap-2 rounded-xl",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ variant = "primary", size = "md", loading, disabled, className = "", children, ...props }, ref) => {
        return (
            <button
                ref={ref}
                disabled={disabled || loading}
                className={`inline-flex items-center justify-center font-medium transition-all duration-150
                    focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500
                    disabled:cursor-not-allowed disabled:shadow-none
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
