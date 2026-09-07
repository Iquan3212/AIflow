import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";

import Logo from "../brand/Logo";

interface Props {
    title: string;
    subtitle: string;
    children: ReactNode;
}

const BENEFITS = [
    "A coordinated AI Workforce, not a single chatbot",
    "Real leads, appointments, and support tickets — not just chat logs",
    "One dashboard for every customer conversation",
];

export default function AuthLayout({ title, subtitle, children }: Props) {
    return (
        <div className="min-h-screen flex bg-white">
            {/* LEFT — brand panel, hidden on small screens */}
            <div className="hidden lg:flex w-1/2 relative overflow-hidden bg-ink-900 text-white p-14 flex-col justify-between">
                <div
                    className="absolute inset-0 pointer-events-none"
                    style={{ background: "radial-gradient(60% 50% at 20% 10%, rgba(139,59,255,0.28) 0%, rgba(5,6,13,0) 70%)" }}
                    aria-hidden="true"
                />
                <div className="relative">
                    <Link to="/" aria-label="AIFlow home">
                        <Logo variant="light" size="md" />
                    </Link>

                    <p className="text-2xl font-display font-semibold mt-16 leading-snug max-w-md">
                        Your business, powered by a coordinated AI Workforce.
                    </p>

                    <ul className="mt-10 space-y-4">
                        {BENEFITS.map((b) => (
                            <li key={b} className="flex items-start gap-3 text-sm text-slate-300">
                                <CheckCircle2 size={18} className="text-brand-300 shrink-0 mt-0.5" aria-hidden="true" />
                                {b}
                            </li>
                        ))}
                    </ul>
                </div>

                <p className="relative text-xs text-slate-500">© {new Date().getFullYear()} AIFlow. All rights reserved.</p>
            </div>

            {/* RIGHT — auth card */}
            <div className="flex-1 flex flex-col justify-center items-center bg-slate-50 px-5 py-12 sm:px-8">
                <div className="w-full max-w-md">
                    <div className="lg:hidden mb-8 flex justify-center">
                        <Link to="/" aria-label="AIFlow home">
                            <Logo size="md" />
                        </Link>
                    </div>

                    <div className="bg-white rounded-3xl shadow-lifted border border-slate-100 w-full p-8 sm:p-10">
                        <h2 className="font-display text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">{title}</h2>
                        <p className="text-slate-500 mt-2.5 mb-8 text-sm">{subtitle}</p>

                        {children}
                    </div>
                </div>
            </div>
        </div>
    );
}
