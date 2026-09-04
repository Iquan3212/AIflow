import type { ReactNode } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import Button from "./Button";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
    return (
        <div className="flex items-center justify-center gap-2 text-slate-500 py-16" role="status" aria-live="polite">
            <Loader2 size={18} className="animate-spin" />
            <span className="text-sm">{label}</span>
        </div>
    );
}

export function ErrorState({
    message = "Something went wrong.",
    onRetry,
}: {
    message?: string;
    onRetry?: () => void;
}) {
    return (
        <div className="flex flex-col items-center justify-center gap-3 text-center py-16 px-6" role="alert">
            <AlertCircle size={28} className="text-red-500" />
            <p className="text-sm text-slate-600 max-w-sm">{message}</p>
            {onRetry && (
                <Button variant="secondary" size="sm" onClick={onRetry}>
                    Try again
                </Button>
            )}
        </div>
    );
}

export function EmptyState({
    icon,
    title,
    description,
    action,
}: {
    icon?: ReactNode;
    title: string;
    description?: string;
    action?: ReactNode;
}) {
    return (
        <div className="flex flex-col items-center justify-center gap-2 text-center py-16 px-6">
            {icon && <div className="text-slate-300 mb-1">{icon}</div>}
            <p className="text-sm font-medium text-slate-700">{title}</p>
            {description && <p className="text-sm text-slate-400 max-w-sm">{description}</p>}
            {action && <div className="mt-3">{action}</div>}
        </div>
    );
}
