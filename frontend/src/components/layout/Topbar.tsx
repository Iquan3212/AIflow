import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, LogOut, Menu } from "lucide-react";

import { useAuth } from "../../context/AuthContext";
import { useBusiness } from "../../context/BusinessContext";

export default function Topbar({ onOpenNav }: { onOpenNav: () => void }) {
    const { business, loading } = useBusiness();
    const { logout } = useAuth();
    const navigate = useNavigate();

    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setMenuOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    async function handleLogout() {
        setMenuOpen(false);
        await logout();
        navigate("/");
    }

    const initial = business?.name?.charAt(0)?.toUpperCase() ?? "?";

    return (
        <header className="h-16 border-b border-slate-200 bg-white flex items-center justify-between px-4 md:px-6 shrink-0">
            <button
                type="button"
                onClick={onOpenNav}
                className="md:hidden text-slate-600 hover:text-slate-900"
                aria-label="Open navigation"
            >
                <Menu size={22} />
            </button>

            <div className="hidden md:block text-sm text-slate-500">
                {loading ? "Loading business…" : business?.name}
            </div>

            <div className="relative" ref={menuRef}>
                <button
                    type="button"
                    onClick={() => setMenuOpen((v) => !v)}
                    className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100"
                    aria-haspopup="menu"
                    aria-expanded={menuOpen}
                >
                    <span className="w-8 h-8 rounded-full bg-indigo-600 text-white text-sm font-semibold flex items-center justify-center">
                        {loading ? "…" : initial}
                    </span>
                    <span className="hidden sm:block text-sm font-medium text-slate-700 max-w-[10rem] truncate">
                        {loading ? "" : business?.name}
                    </span>
                    <ChevronDown size={16} className="text-slate-400" />
                </button>

                {menuOpen && (
                    <div
                        role="menu"
                        className="absolute right-0 mt-2 w-48 rounded-lg border border-slate-200 bg-white shadow-lg py-1 z-20"
                    >
                        <div className="px-3 py-2 border-b border-slate-100">
                            <p className="text-xs text-slate-400">Plan</p>
                            <p className="text-sm font-medium text-slate-700">{business?.plan?.toUpperCase() ?? "—"}</p>
                        </div>
                        <button
                            role="menuitem"
                            onClick={handleLogout}
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                        >
                            <LogOut size={16} />
                            Log out
                        </button>
                    </div>
                )}
            </div>
        </header>
    );
}
