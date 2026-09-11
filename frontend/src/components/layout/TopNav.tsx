import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
    Bot,
    Sparkles,
    Users,
    MessageSquare,
    CalendarClock,
    Workflow,
    FileText,
    LifeBuoy,
    BookOpen,
    BarChart3,
    Settings as SettingsIcon,
    LogOut,
    ChevronDown,
    Menu,
    X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import Logo from "../brand/Logo";
import { useAuth } from "../../context/AuthContext";
import { useAgency } from "../../context/AgencyContext";

interface NavLeaf {
    to: string;
    label: string;
    description: string;
    icon: LucideIcon;
}

interface NavGroup {
    label: string;
    items: NavLeaf[];
}

/** Every entry below maps to a route that actually exists in App.tsx —
 * grouped by job-to-be-done (AI Workforce, Leads, Operations) rather than
 * dumped flat, the way the old 12-item sidebar was. */
const GROUPS: NavGroup[] = [
    {
        label: "AI Workforce",
        items: [
            { to: "/manager", label: "Manager", description: "Chat with the AI that delegates to your specialists.", icon: Bot },
            { to: "/workforce", label: "Employees", description: "See every specialist's status and current task.", icon: Sparkles },
        ],
    },
    {
        label: "Leads",
        items: [
            { to: "/leads", label: "Leads", description: "Every buyer inquiry your AI Workforce has captured.", icon: Users },
            { to: "/conversations", label: "Conversations", description: "Read and reply to customer chats directly.", icon: MessageSquare },
        ],
    },
    {
        label: "Operations",
        items: [
            { to: "/appointments", label: "Site Visits", description: "Scheduled, completed, and cancelled visits.", icon: CalendarClock },
            { to: "/workflows", label: "Workflows", description: "Automations that fire on real events.", icon: Workflow },
            { to: "/drafts", label: "Drafts", description: "AI-written follow-ups awaiting your review.", icon: FileText },
            { to: "/support", label: "Support", description: "Escalated issues that need a human.", icon: LifeBuoy },
        ],
    },
];

const SOLO_LINKS: NavLeaf[] = [
    { to: "/knowledge", label: "Knowledge", description: "", icon: BookOpen },
    { to: "/analytics", label: "Analytics", description: "", icon: BarChart3 },
];

function isGroupActive(group: NavGroup, pathname: string) {
    return group.items.some((item) => pathname.startsWith(item.to));
}

function GroupMenu({ group, pathname }: { group: NavGroup; pathname: string }) {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    const active = isGroupActive(group, pathname);

    useEffect(() => {
        function onDocClick(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        }
        function onKey(e: KeyboardEvent) {
            if (e.key === "Escape") setOpen(false);
        }
        document.addEventListener("mousedown", onDocClick);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onDocClick);
            document.removeEventListener("keydown", onKey);
        };
    }, []);

    return (
        <div className="relative" ref={ref}>
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={open}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    active ? "text-white" : "text-white/70 hover:text-white"
                }`}
            >
                {group.label}
                <ChevronDown size={15} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden="true" />
            </button>

            {open && (
                <div
                    role="menu"
                    className="absolute left-0 top-full mt-2 w-80 rounded-2xl border border-white/10 bg-ink-900/95 backdrop-blur-xl shadow-lifted p-2 origin-top-left animate-[menuOpen_0.16s_ease-out]"
                >
                    {group.items.map((item) => {
                        const Icon = item.icon;
                        const itemActive = pathname.startsWith(item.to);
                        return (
                            <NavLink
                                key={item.to}
                                to={item.to}
                                role="menuitem"
                                onClick={() => setOpen(false)}
                                className={`flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors ${
                                    itemActive ? "bg-white/10" : "hover:bg-white/[0.06]"
                                }`}
                            >
                                <span className="w-9 h-9 rounded-lg bg-white/[0.06] text-flare-400 flex items-center justify-center shrink-0 mt-0.5">
                                    <Icon size={16} aria-hidden="true" />
                                </span>
                                <span className="min-w-0">
                                    <span className="block text-sm font-medium text-white">{item.label}</span>
                                    <span className="block text-xs text-white/50 mt-0.5 leading-snug">{item.description}</span>
                                </span>
                            </NavLink>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

function AccountMenu() {
    const { agency, loading } = useAgency();
    const { logout } = useAuth();
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function onDocClick(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        }
        document.addEventListener("mousedown", onDocClick);
        return () => document.removeEventListener("mousedown", onDocClick);
    }, []);

    async function handleLogout() {
        setOpen(false);
        await logout();
        navigate("/");
    }

    const initial = agency?.name?.charAt(0)?.toUpperCase() ?? "?";

    return (
        <div className="relative" ref={ref}>
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={open}
                className="flex items-center gap-2 rounded-lg pl-2 pr-2.5 py-1.5 hover:bg-white/[0.08] transition-colors"
            >
                <span className="w-7 h-7 rounded-md bg-flare-500 text-ink-950 text-xs font-bold flex items-center justify-center">
                    {loading ? "…" : initial}
                </span>
                <span className="hidden lg:block text-sm font-medium text-white/85 max-w-[9rem] truncate">
                    {loading ? "" : agency?.name}
                </span>
                <ChevronDown size={14} className="text-white/50" aria-hidden="true" />
            </button>

            {open && (
                <div role="menu" className="absolute right-0 top-full mt-2 w-56 rounded-2xl border border-white/10 bg-ink-900/95 backdrop-blur-xl shadow-lifted py-1.5 z-20">
                    <div className="px-3.5 py-2.5 border-b border-white/10">
                        <p className="text-[11px] uppercase tracking-wide text-white/40">Plan</p>
                        <p className="text-sm font-medium text-white/90">{agency?.plan?.toUpperCase() ?? "—"}</p>
                    </div>
                    <NavLink
                        to="/settings"
                        role="menuitem"
                        onClick={() => setOpen(false)}
                        className="flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-white/80 hover:bg-white/[0.06] rounded-lg mx-1 mt-1 transition-colors"
                    >
                        <SettingsIcon size={16} aria-hidden="true" />
                        Settings
                    </NavLink>
                    <button
                        role="menuitem"
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-red-300 hover:bg-red-500/10 rounded-lg mx-1 mb-1 transition-colors"
                        style={{ width: "calc(100% - 0.5rem)" }}
                    >
                        <LogOut size={16} aria-hidden="true" />
                        Log out
                    </button>
                </div>
            )}
        </div>
    );
}

function MobileDrawer({ onClose }: { onClose: () => void }) {
    const pathname = useLocation().pathname;
    const { logout } = useAuth();
    const navigate = useNavigate();

    async function handleLogout() {
        onClose();
        await logout();
        navigate("/");
    }

    const allItems: NavLeaf[] = [
        { to: "/dashboard", label: "Overview", description: "", icon: BarChart3 },
        ...GROUPS.flatMap((g) => g.items),
        ...SOLO_LINKS,
        { to: "/settings", label: "Settings", description: "", icon: SettingsIcon },
    ];

    return (
        <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-ink-950/60" onClick={onClose} aria-hidden="true" />
            <div className="absolute inset-y-0 right-0 w-[85%] max-w-sm bg-ink-950 shadow-lifted flex flex-col">
                <div className="h-16 flex items-center justify-between px-5 border-b border-white/10 shrink-0">
                    <Logo variant="light" size="sm" />
                    <button type="button" onClick={onClose} aria-label="Close navigation" className="text-white/60 hover:text-white">
                        <X size={22} />
                    </button>
                </div>
                <nav aria-label="Primary" className="flex-1 overflow-y-auto p-3 space-y-0.5 thin-scrollbar">
                    {allItems.map(({ to, label, icon: Icon }) => (
                        <NavLink
                            key={to}
                            to={to}
                            onClick={onClose}
                            className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors ${
                                pathname.startsWith(to) ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/[0.06]"
                            }`}
                        >
                            <Icon size={17} aria-hidden="true" />
                            {label}
                        </NavLink>
                    ))}
                </nav>
                <div className="p-3 border-t border-white/10">
                    <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-red-300 hover:bg-red-500/10 transition-colors"
                    >
                        <LogOut size={17} aria-hidden="true" />
                        Log out
                    </button>
                </div>
            </div>
        </div>
    );
}

/** Premium floating top navigation — replaces the old fixed left sidebar.
 * Sticky, glassy, backdrop-blurred; groups become dropdowns on desktop and
 * flatten into one drawer on mobile. */
export default function TopNav() {
    const pathname = useLocation().pathname;
    const [mobileOpen, setMobileOpen] = useState(false);

    return (
        <>
            <header className="sticky top-0 z-30 bg-ink-950/92 backdrop-blur-xl border-b border-white/[0.08]">
                <div className="h-16 px-4 sm:px-6 flex items-center justify-between gap-4 max-w-[100rem] mx-auto">
                    <div className="flex items-center gap-6 min-w-0">
                        <NavLink to="/dashboard" className="shrink-0" aria-label="AIFlow dashboard">
                            <Logo variant="light" size="sm" />
                        </NavLink>

                        <nav aria-label="Primary" className="hidden lg:flex items-center gap-0.5">
                            <NavLink
                                to="/dashboard"
                                end
                                className={({ isActive }) =>
                                    `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                                        isActive ? "text-white" : "text-white/70 hover:text-white"
                                    }`
                                }
                            >
                                Overview
                            </NavLink>
                            {GROUPS.map((group) => (
                                <GroupMenu key={group.label} group={group} pathname={pathname} />
                            ))}
                            {SOLO_LINKS.map((item) => (
                                <NavLink
                                    key={item.to}
                                    to={item.to}
                                    className={({ isActive }) =>
                                        `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                                            isActive ? "text-white" : "text-white/70 hover:text-white"
                                        }`
                                    }
                                >
                                    {item.label}
                                </NavLink>
                            ))}
                        </nav>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                        <div className="hidden lg:block">
                            <AccountMenu />
                        </div>
                        <button
                            type="button"
                            onClick={() => setMobileOpen(true)}
                            className="lg:hidden text-white/80 hover:text-white p-2 -mr-2"
                            aria-label="Open navigation"
                        >
                            <Menu size={22} />
                        </button>
                    </div>
                </div>
            </header>

            {mobileOpen && <MobileDrawer onClose={() => setMobileOpen(false)} />}
        </>
    );
}
