import type { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
    interactive?: boolean;
}

export default function Card({ className = "", interactive = false, ...props }: CardProps) {
    return (
        <div
            className={`bg-white rounded-2xl border border-slate-200/80 shadow-soft ${
                interactive ? "transition-all duration-200 hover:shadow-card hover:border-slate-300" : ""
            } ${className}`}
            {...props}
        />
    );
}
