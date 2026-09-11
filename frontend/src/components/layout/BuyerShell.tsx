import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";

import Logo from "../brand/Logo";
import { useBuyerAuth } from "../../context/BuyerAuthContext";

/** The buyer-facing shell is deliberately its own component, not a themed
 * variant of the agency AppShell/TopNav — buyers must never see agency
 * navigation (Leads, Workflows, Settings…), and an agency owner should
 * never land on marketplace chrome. Two audiences, two shells. */
export default function BuyerShell({ children }: { children: ReactNode }) {
    const { logout } = useBuyerAuth();
    const navigate = useNavigate();

    async function handleLogout() {
        await logout();
        navigate("/discover");
    }

    return (
        <div className="min-h-screen bg-stone-50">
            <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-xl border-b border-slate-200/70">
                <div className="h-16 px-4 sm:px-6 max-w-6xl mx-auto flex items-center justify-between">
                    <Logo size="sm" />
                    <button
                        onClick={handleLogout}
                        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-ink-950 rounded-lg px-3 py-2 hover:bg-slate-100 transition-colors"
                    >
                        <LogOut size={16} aria-hidden="true" />
                        Log out
                    </button>
                </div>
            </header>
            <main className="max-w-6xl mx-auto p-4 sm:p-6 lg:p-9">{children}</main>
        </div>
    );
}
