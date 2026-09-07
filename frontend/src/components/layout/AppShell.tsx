import { useState } from "react";
import type { ReactNode } from "react";

import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppShell({ children }: { children: ReactNode }) {
    const [mobileNavOpen, setMobileNavOpen] = useState(false);

    return (
        <div className="min-h-screen bg-slate-50 flex p-0 md:p-3 gap-3">
            {/* Desktop sidebar — floats with margin instead of a flush edge-to-edge bar */}
            <div className="hidden md:block shrink-0 py-0">
                <Sidebar />
            </div>

            {/* Mobile sidebar drawer — flush, full-height slide-out */}
            {mobileNavOpen && (
                <div className="fixed inset-0 z-30 md:hidden">
                    <div
                        className="absolute inset-0 bg-ink-950/50"
                        onClick={() => setMobileNavOpen(false)}
                        aria-hidden="true"
                    />
                    <div className="absolute inset-y-0 left-0">
                        <Sidebar onNavigate={() => setMobileNavOpen(false)} floating={false} />
                    </div>
                </div>
            )}

            <div className="flex-1 flex flex-col min-w-0 md:rounded-[1.75rem] md:overflow-hidden bg-white md:shadow-soft md:border md:border-slate-200/70">
                <Topbar onOpenNav={() => setMobileNavOpen(true)} />
                <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-9">{children}</main>
            </div>
        </div>
    );
}
