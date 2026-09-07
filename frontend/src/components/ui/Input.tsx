import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
    invalid?: boolean;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
    ({ className = "", invalid = false, ...props }, ref) => {
        return (
            <input
                ref={ref}
                className={`w-full rounded-xl border bg-white px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400
                    transition-colors outline-none
                    focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10
                    disabled:bg-slate-50 disabled:text-slate-400
                    ${invalid ? "border-red-300 focus:border-red-500 focus:ring-red-500/10" : "border-slate-200"}
                    ${className}`}
                {...props}
            />
        );
    }
);
Input.displayName = "Input";

export default Input;

export function Label({ children, htmlFor }: { children: string; htmlFor?: string }) {
    return (
        <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700 mb-1.5">
            {children}
        </label>
    );
}

export function FieldError({ children }: { children?: string }) {
    if (!children) return null;
    return (
        <p className="text-red-600 text-xs mt-1.5" role="alert">
            {children}
        </p>
    );
}
