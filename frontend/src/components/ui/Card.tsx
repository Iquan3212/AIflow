import type { HTMLAttributes } from "react";

export default function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
    return (
        <div
            className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}
            {...props}
        />
    );
}
