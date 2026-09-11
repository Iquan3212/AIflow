import { Bot, TrendingUp, CalendarClock, LifeBuoy, Wallet, BarChart3, Megaphone } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface WorkforceRole {
    id: string;
    name: string;
    description: string;
    icon: LucideIcon;
}

/** The seven real AI Workforce roles this backend actually registers
 * (see backend/app/routers/workforce.py's _DISPLAY_NAMES). Shared between
 * the marketing page and the in-app Workforce page so both describe the
 * exact same roster - no invented specialists. */
export const WORKFORCE_ROLES: WorkforceRole[] = [
    { id: "sales", name: "Sales AI", description: "Answers pricing questions, recommends services, and captures buying interest.", icon: TrendingUp },
    { id: "receptionist", name: "Receptionist AI", description: "Checks availability and books, reschedules, or cancels appointments.", icon: CalendarClock },
    { id: "support", name: "Support AI", description: "Handles customer issues and logs support tickets for your team.", icon: LifeBuoy },
    { id: "finance", name: "Finance AI", description: "Drafts quotations grounded in your real services and pricing.", icon: Wallet },
    { id: "analytics", name: "Analytics AI", description: "Answers questions about your leads, conversations, and activity.", icon: BarChart3 },
    { id: "marketing", name: "Marketing AI", description: "Drafts campaign copy based on your agency and audience.", icon: Megaphone },
];

/** The Manager → Workforce hierarchy diagram. Pure, reusable, and used on
 * both the public landing page and the in-app Workforce page so the
 * concept is introduced once and then confirmed as real inside the app. */
export default function WorkforceDiagram({ variant = "light" }: { variant?: "light" | "dark" }) {
    const isDark = variant === "dark";

    return (
        <div className="w-full">
            <div className="flex flex-col items-center">
                <div
                    className={`inline-flex items-center gap-2.5 rounded-2xl px-5 py-3 shadow-glow ${
                        isDark ? "bg-white text-ink-900" : "bg-ink-900 text-white"
                    }`}
                >
                    <Bot size={20} className="text-brand-500" aria-hidden="true" />
                    <span className="font-display font-semibold text-sm tracking-tight">Manager AI</span>
                </div>
                <div className={`h-8 w-px ${isDark ? "bg-white/25" : "bg-ink-900/15"}`} aria-hidden="true" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4">
                {WORKFORCE_ROLES.map(({ id, name, description, icon: Icon }) => (
                    <div
                        key={id}
                        className={`group rounded-2xl p-4 sm:p-5 transition-all duration-200 ${
                            isDark
                                ? "bg-white/[0.06] border border-white/10 hover:bg-white/[0.09] hover:border-white/20"
                                : "bg-white border border-slate-200/80 shadow-soft hover:shadow-card hover:border-slate-300"
                        }`}
                    >
                        <div
                            className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 transition-transform duration-200 group-hover:scale-105 ${
                                isDark ? "bg-white/10 text-brand-300" : "bg-brand-50 text-brand-600"
                            }`}
                        >
                            <Icon size={18} aria-hidden="true" />
                        </div>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{name}</p>
                        <p className={`text-xs mt-1 leading-relaxed ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                            {description}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    );
}
