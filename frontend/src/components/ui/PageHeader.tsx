import type { ReactNode } from "react";

export default function PageHeader({
    title,
    description,
    actions,
}: {
    title: string;
    description?: string;
    actions?: ReactNode;
}) {
    return (
        <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
            <div>
                <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
                {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
    );
}
