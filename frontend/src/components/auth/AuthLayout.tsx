import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import Logo from "../brand/Logo";

interface Props {
    title: string;
    subtitle: string;
    children: ReactNode;
    /** The decorative strip above the form card. Defaults to the AI
     * Workforce roster (agency auth); pass a different list of labels for
     * a buyer-facing flow, or an empty array to omit the strip entirely. */
    strip?: string[];
}

const AGENCY_STRIP = ["Manager", "Sales", "Reception", "Support", "Finance", "Analytics"];

/** One unified, full-bleed dark canvas instead of the generic "brand panel
 * left / form right" split - the card floats centered over a textured
 * backdrop with a small decorative strip above it, so the brand story and
 * the form aren't two competing halves of the screen. */
export default function AuthLayout({ title, subtitle, children, strip = AGENCY_STRIP }: Props) {
    return (
        <div className="relative min-h-screen bg-ink-950 bg-dot-grid flex flex-col items-center overflow-hidden">
            <div
                className="absolute inset-0 pointer-events-none"
                style={{
                    background:
                        "radial-gradient(70% 50% at 50% 0%, rgba(42,82,64,0.55) 0%, rgba(15,18,15,0) 60%)",
                }}
                aria-hidden="true"
            />

            <header className="relative w-full flex justify-center pt-8 pb-2">
                <Link to="/" aria-label="AIFlow home">
                    <Logo variant="light" size="md" />
                </Link>
            </header>

            <main className="relative flex-1 w-full flex items-center justify-center px-5 py-10">
                <div className="w-full max-w-[26rem]">
                    {/* Decorative strip - a fragment of the relevant concept, not a
                        full competing column */}
                    {strip.length > 0 && (
                        <div className="hidden sm:flex items-center justify-center gap-1.5 mb-6" aria-hidden="true">
                            {strip.map((role, i) => (
                                <span
                                    key={role}
                                    className="text-[11px] font-medium text-slate-400 bg-white/[0.05] border border-white/10 rounded-full px-2.5 py-1"
                                    style={{ opacity: 1 - i * 0.1 }}
                                >
                                    {role}
                                </span>
                            ))}
                        </div>
                    )}

                    <div className="bg-white rounded-3xl shadow-lifted p-8 sm:p-9">
                        <h2 className="font-display text-[1.7rem] font-semibold text-ink-950 tracking-tight leading-tight">
                            {title}
                        </h2>
                        <p className="text-slate-500 mt-2 mb-8 text-sm">{subtitle}</p>

                        {children}
                    </div>
                </div>
            </main>

            <footer className="relative pb-8 text-xs text-slate-500">
                © {new Date().getFullYear()} AIFlow. All rights reserved.
            </footer>
        </div>
    );
}
