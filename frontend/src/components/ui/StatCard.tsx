import type { ReactNode } from "react";
import Card from "./Card";

interface StatCardProps {
    label: string;
    value: ReactNode;
    icon: ReactNode;
    hint?: string;
}

export default function StatCard({ label, value, icon, hint }: StatCardProps) {
    return (
        <Card className="p-5" interactive>
            <div className="flex items-start justify-between">
                <div className="min-w-0">
                    <p className="text-sm text-slate-500">{label}</p>
                    <p className="text-2xl font-semibold text-slate-900 mt-1.5 tracking-tight">{value}</p>
                    {hint && <p className="text-xs text-slate-400 mt-1.5">{hint}</p>}
                </div>
                <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center shrink-0">
                    {icon}
                </div>
            </div>
        </Card>
    );
}
