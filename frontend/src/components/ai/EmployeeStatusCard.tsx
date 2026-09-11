import { Bot, TrendingUp, CalendarClock, LifeBuoy, Wallet, BarChart3, Megaphone, Users2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import StatusIndicator from "./StatusIndicator";
import type { EmployeeInfo } from "../../types/ai";

const ROLE_ICONS: Record<string, LucideIcon> = {
    manager: Bot,
    sales: TrendingUp,
    receptionist: CalendarClock,
    support: LifeBuoy,
    finance: Wallet,
    analytics: BarChart3,
    marketing: Megaphone,
};

/** A distinct accent per role (order matches the real registry:
 * app/routers/workforce.py) so the roster reads as a team of specialists,
 * not seven copies of one template — while every card still shares the
 * same structure/typography, one design system throughout. */
const ROLE_ACCENT: Record<string, string> = {
    sales: "text-brand-600 bg-brand-50",
    receptionist: "text-sky-600 bg-sky-50",
    support: "text-amber-600 bg-amber-50",
    finance: "text-flare-600 bg-flare-50",
    analytics: "text-violet-600 bg-violet-50",
    marketing: "text-rose-600 bg-rose-50",
};

export default function EmployeeStatusCard({ employee, highlight = false }: { employee: EmployeeInfo; highlight?: boolean }) {
    const Icon = ROLE_ICONS[employee.id] ?? Users2;
    const accent = ROLE_ACCENT[employee.id] ?? "text-brand-600 bg-brand-50";

    return (
        <div
            className={`rounded-2xl p-5 transition-all duration-200 ${
                highlight
                    ? "bg-ink-950 text-white shadow-lifted"
                    : "bg-white border border-slate-200/80 shadow-soft hover:shadow-card hover:border-slate-300"
            }`}
        >
            <div className="flex items-center gap-3">
                <div
                    className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
                        highlight ? "bg-white/10 text-flare-400" : accent
                    }`}
                >
                    <Icon size={20} aria-hidden="true" />
                </div>
                <div className="min-w-0">
                    <div className={`text-sm font-semibold truncate ${highlight ? "text-white" : "text-slate-900"}`}>
                        {employee.name}
                    </div>
                    <div className={`text-xs flex items-center gap-1.5 ${highlight ? "text-slate-400" : "text-slate-500"}`}>
                        <StatusIndicator status={employee.status} />
                        <span className="capitalize">{employee.status}</span>
                    </div>
                </div>
            </div>

            {employee.current_task && (
                <p className={`mt-3 text-sm ${highlight ? "text-slate-300" : "text-slate-600"}`}>{employee.current_task}</p>
            )}

            {employee.confidence != null && (
                <p className={`mt-2 text-xs ${highlight ? "text-slate-400" : "text-slate-400"}`}>
                    Confidence:{" "}
                    <span className={highlight ? "text-white font-medium" : "text-slate-600 font-medium"}>
                        {Math.round(employee.confidence * 100)}%
                    </span>
                </p>
            )}

            {employee.tools && employee.tools.length > 0 && (
                <div className="mt-3.5 flex flex-wrap gap-1.5">
                    {employee.tools.map((t) => (
                        <span
                            key={t}
                            className={`text-xs rounded-md px-2.5 py-1 ${
                                highlight ? "bg-white/10 text-slate-300" : "bg-slate-100 text-slate-600"
                            }`}
                        >
                            {t}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
