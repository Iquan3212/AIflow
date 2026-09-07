import { NavLink } from "react-router-dom";
import {
    LayoutDashboard,
    Users,
    MessageSquare,
    CalendarClock,
    Bot,
    Sparkles,
    BarChart3,
    FileText,
    LifeBuoy,
    Settings,
    X,
} from "lucide-react";

import Logo from "../brand/Logo";

const NAV_ITEMS = [
    { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/workforce", label: "AI Workforce", icon: Sparkles },
    { to: "/manager", label: "Manager AI", icon: Bot },
    { to: "/conversations", label: "Conversations", icon: MessageSquare },
    { to: "/leads", label: "Leads", icon: Users },
    { to: "/appointments", label: "Appointments", icon: CalendarClock },
    { to: "/drafts", label: "Drafts", icon: FileText },
    { to: "/support", label: "Support", icon: LifeBuoy },
    { to: "/analytics", label: "Analytics", icon: BarChart3 },
    { to: "/settings", label: "Settings", icon: Settings },
];

/** A floating, rounded panel inset from the viewport edge - not the classic
 * flush-left dark bar every dashboard template ships with. */
export default function Sidebar({ onNavigate, floating = true }: { onNavigate?: () => void; floating?: boolean }) {
    return (
        <nav
            aria-label="Primary"
            className={`flex flex-col h-full bg-ink-950 text-slate-300 w-64 ${
                floating ? "rounded-[1.75rem] shadow-lifted" : ""
            }`}
        >
            <div className="h-16 flex items-center justify-between px-5 shrink-0">
                <Logo variant="light" size="sm" />
                <button
                    type="button"
                    onClick={onNavigate}
                    className="md:hidden text-slate-400 hover:text-white"
                    aria-label="Close navigation"
                >
                    <X size={20} />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto py-2 px-3 space-y-0.5 thin-scrollbar">
                {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                    <NavLink
                        key={to}
                        to={to}
                        onClick={onNavigate}
                        className={({ isActive }) =>
                            `flex items-center gap-3 rounded-full px-4 py-2.5 text-sm font-medium transition-colors ${
                                isActive
                                    ? "bg-white text-ink-950"
                                    : "text-slate-400 hover:bg-white/[0.07] hover:text-white"
                            }`
                        }
                    >
                        <Icon size={17} aria-hidden="true" />
                        {label}
                    </NavLink>
                ))}
            </div>

            <div className="p-3">
                <div className="rounded-2xl bg-white/[0.05] border border-white/10 px-4 py-3.5">
                    <p className="text-xs text-slate-500">Powered by</p>
                    <p className="text-sm font-display font-semibold text-white mt-0.5">AI Workforce</p>
                </div>
            </div>
        </nav>
    );
}
