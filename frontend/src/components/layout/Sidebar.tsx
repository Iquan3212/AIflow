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
    Settings,
    X,
} from "lucide-react";

const NAV_ITEMS = [
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { to: "/workforce", label: "AI Workforce", icon: Sparkles },
    { to: "/manager", label: "Manager AI", icon: Bot },
    { to: "/leads", label: "Leads", icon: Users },
    { to: "/conversations", label: "Conversations", icon: MessageSquare },
    { to: "/appointments", label: "Appointments", icon: CalendarClock },
    { to: "/drafts", label: "Drafts", icon: FileText },
    { to: "/analytics", label: "Analytics", icon: BarChart3 },
    { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
    return (
        <nav aria-label="Primary" className="flex flex-col h-full bg-slate-900 text-slate-300 w-64">
            <div className="h-16 flex items-center justify-between px-5 border-b border-slate-800 shrink-0">
                <span className="text-white font-semibold tracking-tight">AIFlow</span>
                <button
                    type="button"
                    onClick={onNavigate}
                    className="md:hidden text-slate-400 hover:text-white"
                    aria-label="Close navigation"
                >
                    <X size={20} />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
                {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                    <NavLink
                        key={to}
                        to={to}
                        onClick={onNavigate}
                        className={({ isActive }) =>
                            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                                isActive
                                    ? "bg-indigo-600 text-white"
                                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                            }`
                        }
                    >
                        <Icon size={18} />
                        {label}
                    </NavLink>
                ))}
            </div>
        </nav>
    );
}
