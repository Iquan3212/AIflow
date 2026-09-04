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
        <Card className="p-5">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-sm text-slate-500">{label}</p>
                    <p className="text-2xl font-semibold text-slate-900 mt-1">{value}</p>
                    {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
                </div>
                <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                    {icon}
                </div>
            </div>
        </Card>
    );
}
