import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import {
    Bot, ClipboardList, Compass, Home as HomeIcon, LayoutGrid,
    LogOut, Menu, Scale, User, X,
} from "lucide-react";

import Logo from "../brand/Logo";
import Button from "../ui/Button";
import { useBuyerAuth } from "../../context/BuyerAuthContext";
import { useCompare } from "../../context/CompareContext";

/** The buyer product's own navigation shell - deliberately not a themed
 * variant of the agency AppShell/TopNav (see the old BuyerShell's
 * comment, preserved in spirit here): a buyer must never see Leads,
 * Workflows, Settings, etc., and this component must never be reused on
 * an agency-authenticated route. Adapts to auth state rather than being
 * two separate components, since Discover/project/property pages are
 * genuinely public and need the exact same brand chrome whether or not
 * a buyer happens to be signed in. */

const NAV_ITEMS = [
    { to: "/buyer/home", label: "Home", icon: HomeIcon },
    { to: "/discover", label: "Discover", icon: Compass },
    { to: "/buyer/saved", label: "Saved", icon: LayoutGrid },
    { to: "/buyer/compare", label: "Compare", icon: Scale },
    { to: "/buyer/activity", label: "My Activity", icon: ClipboardList },
];

const MOBILE_TAB_ITEMS = [
    { to: "/buyer/home", label: "Home", icon: HomeIcon },
    { to: "/discover", label: "Discover", icon: Compass },
    { to: "/buyer/saved", label: "Saved", icon: LayoutGrid },
    { to: "/buyer/activity", label: "Activity", icon: ClipboardList },
    { to: "/buyer/assistant", label: "AI", icon: Bot },
];

function navLinkClass({ isActive }: { isActive: boolean }) {
    return `relative px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
        isActive ? "text-ink-950 bg-stone-100" : "text-slate-600 hover:text-ink-950 hover:bg-stone-50"
    }`;
}

export default function BuyerNav() {
    const { isAuthenticated, logout } = useBuyerAuth();
    const { ids } = useCompare();
    const navigate = useNavigate();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [profileOpen, setProfileOpen] = useState(false);

    useEffect(() => {
        if (!profileOpen && !mobileOpen) return;
        function handleKey(e: KeyboardEvent) {
            if (e.key === "Escape") {
                setProfileOpen(false);
                setMobileOpen(false);
            }
        }
        document.addEventListener("keydown", handleKey);
        return () => document.removeEventListener("keydown", handleKey);
    }, [profileOpen, mobileOpen]);

    async function handleLogout() {
        setProfileOpen(false);
        setMobileOpen(false);
        await logout();
        navigate("/discover");
    }

    return (
        <>
            <header className="border-b border-slate-200/70 bg-white/85 backdrop-blur-xl sticky top-0 z-30">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-6 min-w-0">
                        <Link to={isAuthenticated ? "/buyer/home" : "/discover"} aria-label="AIFlow" className="shrink-0">
                            <Logo size="sm" />
                        </Link>

                        {isAuthenticated && (
                            <nav className="hidden lg:flex items-center gap-1" aria-label="Buyer navigation">
                                {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                                    <NavLink key={to} to={to} className={navLinkClass}>
                                        <span className="inline-flex items-center gap-1.5">
                                            <Icon size={14} aria-hidden="true" />
                                            {label}
                                            {to === "/buyer/compare" && ids.length > 0 && (
                                                <span className="inline-flex items-center justify-center min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-flare-500 text-ink-950 text-[10px] font-bold">
                                                    {ids.length}
                                                </span>
                                            )}
                                        </span>
                                    </NavLink>
                                ))}
                            </nav>
                        )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                        {isAuthenticated ? (
                            <>
                                <Link to="/buyer/assistant" className="hidden sm:block">
                                    <Button size="sm" variant="flare">
                                        <Bot size={15} aria-hidden="true" /> AI Assistant
                                    </Button>
                                </Link>

                                <div className="relative hidden lg:block">
                                    <button
                                        type="button"
                                        onClick={() => setProfileOpen((v) => !v)}
                                        aria-haspopup="menu"
                                        aria-expanded={profileOpen}
                                        aria-label="Profile menu"
                                        className="w-9 h-9 rounded-full bg-stone-100 text-slate-600 flex items-center justify-center hover:bg-stone-200 transition-colors"
                                    >
                                        <User size={16} aria-hidden="true" />
                                    </button>
                                    {profileOpen && (
                                        <>
                                            <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} aria-hidden="true" />
                                            <div
                                                role="menu"
                                                style={{ animation: "menuOpen 0.15s ease-out" }}
                                                className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lifted border border-slate-100 py-1.5 z-20"
                                            >
                                                <Link
                                                    to="/buyer/profile"
                                                    role="menuitem"
                                                    onClick={() => setProfileOpen(false)}
                                                    className="flex items-center gap-2 px-3.5 py-2 text-sm text-slate-700 hover:bg-stone-50"
                                                >
                                                    <User size={14} aria-hidden="true" /> Profile &amp; settings
                                                </Link>
                                                <button
                                                    type="button"
                                                    role="menuitem"
                                                    onClick={handleLogout}
                                                    className="w-full flex items-center gap-2 px-3.5 py-2 text-sm text-slate-700 hover:bg-stone-50"
                                                >
                                                    <LogOut size={14} aria-hidden="true" /> Sign out
                                                </button>
                                            </div>
                                        </>
                                    )}
                                </div>

                                <button
                                    type="button"
                                    onClick={() => setMobileOpen(true)}
                                    aria-label="Open menu"
                                    className="lg:hidden w-9 h-9 rounded-full bg-stone-100 text-slate-600 flex items-center justify-center"
                                >
                                    <Menu size={17} aria-hidden="true" />
                                </button>
                            </>
                        ) : (
                            <>
                                <Link to="/buyer/login" className="text-sm font-semibold text-slate-700 hover:text-ink-950 px-3.5 py-2">
                                    Sign in
                                </Link>
                                <Link to="/buyer/register">
                                    <Button size="sm" variant="flare">Create account</Button>
                                </Link>
                            </>
                        )}
                    </div>
                </div>
            </header>

            {/* Mobile menu sheet - the desktop nav's items plus profile/sign out,
                since the top bar has no room for a full link list at phone width. */}
            {isAuthenticated && mobileOpen && (
                <div className="fixed inset-0 z-40 lg:hidden">
                    <div className="absolute inset-0 bg-ink-950/50" onClick={() => setMobileOpen(false)} aria-hidden="true" />
                    <div className="absolute right-0 top-0 bottom-0 w-72 max-w-[85vw] bg-white shadow-lifted flex flex-col">
                        <div className="h-16 px-4 flex items-center justify-between border-b border-slate-100">
                            <Logo size="sm" />
                            <button
                                type="button"
                                onClick={() => setMobileOpen(false)}
                                aria-label="Close menu"
                                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-500 hover:bg-stone-100"
                            >
                                <X size={18} />
                            </button>
                        </div>
                        <nav className="flex-1 overflow-y-auto py-2" aria-label="Buyer navigation">
                            {[...NAV_ITEMS, { to: "/buyer/assistant", label: "AI Assistant", icon: Bot }].map(
                                ({ to, label, icon: Icon }) => (
                                    <NavLink
                                        key={to}
                                        to={to}
                                        onClick={() => setMobileOpen(false)}
                                        className={({ isActive }) =>
                                            `flex items-center gap-3 px-5 py-3 text-sm font-medium ${
                                                isActive ? "text-ink-950 bg-stone-50" : "text-slate-600"
                                            }`
                                        }
                                    >
                                        <Icon size={16} aria-hidden="true" />
                                        {label}
                                        {to === "/buyer/compare" && ids.length > 0 && (
                                            <span className="ml-auto inline-flex items-center justify-center min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-flare-500 text-ink-950 text-[10px] font-bold">
                                                {ids.length}
                                            </span>
                                        )}
                                    </NavLink>
                                )
                            )}
                        </nav>
                        <div className="border-t border-slate-100 p-2">
                            <Link
                                to="/buyer/profile"
                                onClick={() => setMobileOpen(false)}
                                className="flex items-center gap-3 px-3 py-3 text-sm font-medium text-slate-700 rounded-lg hover:bg-stone-50"
                            >
                                <User size={16} aria-hidden="true" /> Profile &amp; settings
                            </Link>
                            <button
                                type="button"
                                onClick={handleLogout}
                                className="w-full flex items-center gap-3 px-3 py-3 text-sm font-medium text-slate-700 rounded-lg hover:bg-stone-50"
                            >
                                <LogOut size={16} aria-hidden="true" /> Sign out
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Mobile bottom tab bar - the core five destinations, always in
                thumb reach; hidden on desktop where the top nav already covers
                everything. Hidden entirely when signed out, same as the rest
                of the buyer chrome. */}
            {isAuthenticated && (
                <nav
                    aria-label="Buyer navigation"
                    className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-white/95 backdrop-blur-xl border-t border-slate-200/70 pb-[env(safe-area-inset-bottom)]"
                >
                    <div className="grid grid-cols-5">
                        {MOBILE_TAB_ITEMS.map(({ to, label, icon: Icon }) => (
                            <NavLink
                                key={to}
                                to={to}
                                className={({ isActive }) =>
                                    `flex flex-col items-center justify-center gap-0.5 py-2.5 text-[11px] font-medium ${
                                        isActive ? "text-brand-600" : "text-slate-500"
                                    }`
                                }
                            >
                                <Icon size={19} aria-hidden="true" />
                                {label}
                            </NavLink>
                        ))}
                    </div>
                </nav>
            )}
        </>
    );
}
