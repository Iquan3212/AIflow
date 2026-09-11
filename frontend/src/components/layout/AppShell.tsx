import type { ReactNode } from "react";

import TopNav from "./TopNav";

export default function AppShell({ children }: { children: ReactNode }) {
    return (
        <div className="min-h-screen bg-slate-100">
            <TopNav />
            <main className="max-w-[100rem] mx-auto p-4 sm:p-6 lg:p-9">{children}</main>
        </div>
    );
}
