import type { ReactNode } from "react";

export default function PageHeader({
    title,
    description,
    actions,
    eyebrow,
}: {
    title: string;
    description?: string;
    actions?: ReactNode;
    eyebrow?: string;
}) {
    return (
        <div className="flex items-start justify-between gap-4 flex-wrap mb-8">
            <div>
                {eyebrow && (
                    <p className="text-xs font-semibold uppercase tracking-wide text-brand-600 mb-1.5">
                        {eyebrow}
                    </p>
                )}
                <h1 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">{title}</h1>
                {description && <p className="text-sm text-slate-500 mt-1.5 max-w-2xl">{description}</p>}
            </div>
            {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
    );
}
