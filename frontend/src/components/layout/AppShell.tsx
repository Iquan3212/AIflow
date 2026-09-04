import { useState } from "react";
import type { ReactNode } from "react";

import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppShell({ children }: { children: ReactNode }) {
    const [mobileNavOpen, setMobileNavOpen] = useState(false);

    return (
        <div className="min-h-screen bg-slate-50 flex">
            {/* Desktop sidebar */}
            <div className="hidden md:block shrink-0">
                <Sidebar />
            </div>

            {/* Mobile sidebar drawer */}
            {mobileNavOpen && (
                <div className="fixed inset-0 z-30 md:hidden">
                    <div
                        className="absolute inset-0 bg-slate-900/50"
                        onClick={() => setMobileNavOpen(false)}
                        aria-hidden="true"
                    />
                    <div className="absolute inset-y-0 left-0">
                        <Sidebar onNavigate={() => setMobileNavOpen(false)} />
                    </div>
                </div>
            )}

            <div className="flex-1 flex flex-col min-w-0">
                <Topbar onOpenNav={() => setMobileNavOpen(true)} />
                <main className="flex-1 overflow-y-auto p-4 md:p-8">{children}</main>
            </div>
        </div>
    );
}
