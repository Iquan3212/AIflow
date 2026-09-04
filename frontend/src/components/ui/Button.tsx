import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: Variant;
    size?: Size;
    loading?: boolean;
}

const VARIANT_CLASSES: Record<Variant, string> = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300",
    secondary: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 disabled:text-slate-400",
    ghost: "bg-transparent text-slate-600 hover:bg-slate-100 disabled:text-slate-300",
    danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300",
};

const SIZE_CLASSES: Record<Size, string> = {
    sm: "text-sm px-3 py-1.5 gap-1.5",
    md: "text-sm px-4 py-2.5 gap-2",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ variant = "primary", size = "md", loading, disabled, className = "", children, ...props }, ref) => {
        return (
            <button
                ref={ref}
                disabled={disabled || loading}
                className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors
                    focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500
                    disabled:cursor-not-allowed
                    ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
                {...props}
            >
                {loading && <Loader2 size={16} className="animate-spin" />}
                {children}
            </button>
        );
    }
);
Button.displayName = "Button";

export default Button;
