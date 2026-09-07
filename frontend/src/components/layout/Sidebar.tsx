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

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
    return (
        <nav aria-label="Primary" className="flex flex-col h-full bg-ink-900 text-slate-300 w-64">
            <div className="h-16 flex items-center justify-between px-5 border-b border-white/[0.06] shrink-0">
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

            <div className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5 thin-scrollbar">
                {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                    <NavLink
                        key={to}
                        to={to}
                        onClick={onNavigate}
                        className={({ isActive }) =>
                            `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                                isActive
                                    ? "bg-brand-600 text-white shadow-soft"
                                    : "text-slate-400 hover:bg-white/[0.06] hover:text-white"
                            }`
                        }
                    >
                        <Icon size={18} aria-hidden="true" />
                        {label}
                    </NavLink>
                ))}
            </div>
        </nav>
    );
}
