import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
    ArrowRight,
    MessageSquare,
    Users,
    CalendarClock,
    LifeBuoy,
    BarChart3,
    FileText,
    Globe,
    ShieldCheck,
    KeyRound,
    Database,
    Eye,
    Menu,
    X,
} from "lucide-react";

import Logo from "../../components/brand/Logo";
import WorkforceDiagram from "../../components/brand/WorkforceDiagram";
import Button from "../../components/ui/Button";

const NAV_LINKS = [
    { href: "#workforce", label: "AI Workforce" },
    { href: "#features", label: "Features" },
    { href: "#how-it-works", label: "How It Works" },
    { href: "#channels", label: "Channels" },
];

function fadeUp(reduced: boolean | null) {
    if (reduced) return {};
    return {
        initial: { opacity: 0, y: 18 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, margin: "-80px" },
        transition: { duration: 0.5, ease: "easeOut" as const },
    };
}

export default function Landing() {
    const reduced = useReducedMotion();
    const [scrolled, setScrolled] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);

    useEffect(() => {
        function onScroll() {
            setScrolled(window.scrollY > 8);
        }
        onScroll();
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    return (
        <div className="bg-white text-ink-900">
            {/* ================= NAVBAR ================= */}
            <header
                className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
                    scrolled ? "bg-white/85 backdrop-blur-md border-b border-slate-200/80 shadow-soft" : "bg-transparent"
                }`}
            >
                <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
                    <Link to="/" aria-label="AIFlow home">
                        <Logo size="sm" />
                    </Link>

                    <nav aria-label="Primary" className="hidden md:flex items-center gap-8">
                        {NAV_LINKS.map((link) => (
                            <a
                                key={link.href}
                                href={link.href}
                                className="text-sm font-medium text-slate-600 hover:text-ink-900 transition-colors"
                            >
                                {link.label}
                            </a>
                        ))}
                    </nav>

                    <div className="hidden md:flex items-center gap-3">
                        <Link to="/login" className="text-sm font-medium text-slate-600 hover:text-ink-900 px-3 py-2 transition-colors">
                            Sign In
                        </Link>
                        <Link to="/register">
                            <Button size="sm">Get Started</Button>
                        </Link>
                    </div>

                    <button
                        type="button"
                        className="md:hidden text-slate-700 p-2"
                        aria-label={mobileOpen ? "Close menu" : "Open menu"}
                        aria-expanded={mobileOpen}
                        onClick={() => setMobileOpen((v) => !v)}
                    >
                        {mobileOpen ? <X size={22} /> : <Menu size={22} />}
                    </button>
                </div>

                {mobileOpen && (
                    <div className="md:hidden bg-white border-t border-slate-200 px-5 py-4 flex flex-col gap-1">
                        {NAV_LINKS.map((link) => (
                            <a
                                key={link.href}
                                href={link.href}
                                onClick={() => setMobileOpen(false)}
                                className="text-sm font-medium text-slate-700 px-2 py-2.5 rounded-lg hover:bg-slate-50"
                            >
                                {link.label}
                            </a>
                        ))}
                        <div className="border-t border-slate-100 mt-2 pt-3 flex flex-col gap-2">
                            <Link to="/login" onClick={() => setMobileOpen(false)}>
                                <Button variant="secondary" className="w-full">Sign In</Button>
                            </Link>
                            <Link to="/register" onClick={() => setMobileOpen(false)}>
                                <Button className="w-full">Get Started</Button>
                            </Link>
                        </div>
                    </div>
                )}
            </header>

            {/* ================= HERO ================= */}
            <section className="relative overflow-hidden bg-ink-900 pt-36 pb-24 sm:pt-44 sm:pb-32">
                <div
                    className="absolute inset-0 pointer-events-none"
                    style={{
                        background:
                            "radial-gradient(60% 50% at 50% 0%, rgba(139,59,255,0.28) 0%, rgba(5,6,13,0) 70%)",
                    }}
                    aria-hidden="true"
                />
                <div className="relative max-w-5xl mx-auto px-5 sm:px-8 text-center">
                    <motion.div {...fadeUp(reduced)}>
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.06] border border-white/10 px-3.5 py-1.5 text-xs font-medium text-slate-300">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                            An AI Workforce for growing businesses
                        </span>
                    </motion.div>

                    <motion.h1
                        {...fadeUp(reduced)}
                        transition={{ ...fadeUp(reduced).transition, delay: 0.05 }}
                        className="font-display text-4xl sm:text-6xl font-bold tracking-tight text-white mt-6 leading-[1.08]"
                    >
                        Your business, powered by
                        <br className="hidden sm:block" /> an AI Workforce.
                    </motion.h1>

                    <motion.p
                        {...fadeUp(reduced)}
                        transition={{ ...fadeUp(reduced).transition, delay: 0.1 }}
                        className="text-lg text-slate-300 mt-6 max-w-2xl mx-auto leading-relaxed"
                    >
                        Instead of one generic chatbot, AIFlow gives your business a coordinated team of
                        specialized AI employees — handling customer conversations, leads, appointments,
                        support and analytics, all managed from one dashboard.
                    </motion.p>

                    <motion.div
                        {...fadeUp(reduced)}
                        transition={{ ...fadeUp(reduced).transition, delay: 0.15 }}
                        className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-9"
                    >
                        <Link to="/register" className="w-full sm:w-auto">
                            <Button size="lg" className="w-full sm:w-auto">
                                Start Free <ArrowRight size={18} />
                            </Button>
                        </Link>
                        <a href="#how-it-works" className="w-full sm:w-auto">
                            <Button size="lg" variant="secondary" className="w-full sm:w-auto !bg-white/[0.06] !text-white !border-white/15 hover:!bg-white/10">
                                See How It Works
                            </Button>
                        </a>
                    </motion.div>
                </div>

                {/* Hero visual: the real AI Workforce hierarchy, not a fabricated product screenshot */}
                <motion.div
                    {...fadeUp(reduced)}
                    transition={{ ...fadeUp(reduced).transition, delay: 0.2 }}
                    className="relative max-w-4xl mx-auto px-5 sm:px-8 mt-16 sm:mt-20"
                >
                    <WorkforceDiagram variant="dark" />
                </motion.div>
            </section>

            {/* ================= PROBLEM ================= */}
            <section className="py-24 sm:py-28 bg-white">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...fadeUp(reduced)} className="max-w-2xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">The problem</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-3">
                            Running a business means operations pile up faster than your team can keep up.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-12">
                        {[
                            { title: "Leads go cold", body: "A slow reply is often the difference between a customer and a missed sale." },
                            { title: "Customers wait", body: "Website chats, WhatsApp and Instagram messages pile up outside business hours." },
                            { title: "Scheduling is manual", body: "Appointments get juggled by hand, with no single source of truth." },
                            { title: "Data lives everywhere", body: "Leads, conversations and follow-ups are scattered across tools and inboxes." },
                        ].map((item, i) => (
                            <motion.div
                                key={item.title}
                                {...fadeUp(reduced)}
                                transition={{ ...fadeUp(reduced).transition, delay: i * 0.05 }}
                                className="rounded-2xl border border-slate-200/80 p-6 bg-slate-50/60"
                            >
                                <p className="font-semibold text-slate-900">{item.title}</p>
                                <p className="text-sm text-slate-500 mt-2 leading-relaxed">{item.body}</p>
                            </motion.div>
                        ))}
                    </div>

                    <motion.p
                        {...fadeUp(reduced)}
                        className="text-center font-display text-xl sm:text-2xl font-semibold mt-14 text-ink-900"
                    >
                        AIFlow brings these operations together — under one coordinated AI Workforce.
                    </motion.p>
                </div>
            </section>

            {/* ================= AI WORKFORCE ================= */}
            <section id="workforce" className="py-24 sm:py-28 bg-slate-50 scroll-mt-16">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...fadeUp(reduced)} className="max-w-2xl mx-auto text-center">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">The AI Workforce</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-3">
                            One Manager. Six specialists. Zero context switching.
                        </h2>
                        <p className="text-slate-500 mt-4 leading-relaxed">
                            A Manager AI reads every conversation, decides which specialist should handle it,
                            and coordinates the reply — so customers always get a focused answer instead of a
                            generic one.
                        </p>
                    </motion.div>

                    <motion.div {...fadeUp(reduced)} className="mt-14 max-w-4xl mx-auto">
                        <WorkforceDiagram variant="light" />
                    </motion.div>
                </div>
            </section>

            {/* ================= HOW IT WORKS ================= */}
            <section id="how-it-works" className="py-24 sm:py-28 bg-white scroll-mt-16">
                <div className="max-w-5xl mx-auto px-5 sm:px-8">
                    <motion.div {...fadeUp(reduced)} className="max-w-2xl mx-auto text-center">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">How it works</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-3">
                            Set up your AI Workforce in minutes.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 mt-14">
                        {[
                            { step: "01", title: "Connect your business", body: "Sign up and tell AIFlow about your business — services, tone, and hours." },
                            { step: "02", title: "Configure your Workforce", body: "Manager AI is ready immediately; each specialist grounds its answers in your data." },
                            { step: "03", title: "Connect your channels", body: "Bring in your website chat, WhatsApp, and Instagram as they're needed." },
                            { step: "04", title: "Stay in control", body: "Review conversations, leads, and drafts from one dashboard — the AI never acts unsupervised." },
                        ].map((item, i) => (
                            <motion.div
                                key={item.step}
                                {...fadeUp(reduced)}
                                transition={{ ...fadeUp(reduced).transition, delay: i * 0.06 }}
                                className="relative"
                            >
                                <span className="font-display text-4xl font-bold text-slate-200">{item.step}</span>
                                <p className="font-semibold text-slate-900 mt-3">{item.title}</p>
                                <p className="text-sm text-slate-500 mt-2 leading-relaxed">{item.body}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ================= FEATURES ================= */}
            <section id="features" className="py-24 sm:py-28 bg-slate-50 scroll-mt-16">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...fadeUp(reduced)} className="max-w-2xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">What's included</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-3">
                            Everything your AI Workforce needs to actually get work done.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 mt-12">
                        {[
                            { icon: MessageSquare, title: "Customer conversations", body: "Every message — from any channel — lands in one unified conversation history." },
                            { icon: Users, title: "Lead management", body: "Sales AI captures interest and contact details as real, reviewable leads." },
                            { icon: CalendarClock, title: "Appointments", body: "Receptionist AI checks real availability before booking, rescheduling, or cancelling." },
                            { icon: LifeBuoy, title: "Support tickets", body: "Support AI logs every issue as a ticket your team can track and resolve." },
                            { icon: FileText, title: "AI-drafted content", body: "Finance and Marketing AI prepare quotations and campaign copy for your review." },
                            { icon: BarChart3, title: "Business analytics", body: "Ask Analytics AI about your real leads, conversations, and activity — in plain language." },
                        ].map((item, i) => (
                            <motion.div
                                key={item.title}
                                {...fadeUp(reduced)}
                                transition={{ ...fadeUp(reduced).transition, delay: (i % 3) * 0.06 }}
                                className="rounded-2xl bg-white border border-slate-200/80 shadow-soft p-6 hover:shadow-card hover:border-slate-300 transition-all duration-200"
                            >
                                <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
                                    <item.icon size={19} aria-hidden="true" />
                                </div>
                                <p className="font-semibold text-slate-900 mt-4">{item.title}</p>
                                <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{item.body}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ================= CHANNELS ================= */}
            <section id="channels" className="py-24 sm:py-28 bg-ink-900 text-white scroll-mt-16">
                <div className="max-w-5xl mx-auto px-5 sm:px-8 text-center">
                    <motion.div {...fadeUp(reduced)}>
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-300">Multi-channel, one conversation</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-3">
                            Wherever a customer reaches out, your Workforce is there.
                        </h2>
                        <p className="text-slate-400 mt-4 max-w-xl mx-auto leading-relaxed">
                            Website chat, WhatsApp, and Instagram all feed into the same customer conversation
                            and the same Manager AI — so context is never lost between channels.
                        </p>
                    </motion.div>

                    <motion.div
                        {...fadeUp(reduced)}
                        className="mt-14 flex flex-col items-center gap-4"
                    >
                        <div className="flex flex-wrap items-center justify-center gap-3">
                            {["Website", "WhatsApp", "Instagram"].map((ch) => (
                                <span
                                    key={ch}
                                    className="inline-flex items-center gap-2 rounded-full bg-white/[0.06] border border-white/10 px-4 py-2 text-sm font-medium"
                                >
                                    <Globe size={15} className="text-brand-300" aria-hidden="true" />
                                    {ch}
                                </span>
                            ))}
                        </div>
                        <div className="h-8 w-px bg-white/15" aria-hidden="true" />
                        <div className="inline-flex items-center gap-2 rounded-full bg-brand-500/15 border border-brand-400/30 px-4 py-2 text-sm font-medium text-brand-200">
                            Unified conversation
                        </div>
                        <div className="h-8 w-px bg-white/15" aria-hidden="true" />
                        <div className="inline-flex items-center gap-2.5 rounded-2xl bg-white text-ink-900 px-5 py-3 shadow-glow font-display font-semibold text-sm">
                            Manager AI
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* ================= BENEFITS ================= */}
            <section className="py-24 sm:py-28 bg-white">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...fadeUp(reduced)} className="max-w-2xl mx-auto text-center">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Why it matters</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-3">
                            Built around business outcomes, not technology.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 mt-12">
                        {[
                            "Respond to customers faster, around the clock",
                            "Capture more leads instead of losing them to silence",
                            "Reduce repetitive work for your team",
                            "Never miss a follow-up",
                            "Coordinate every customer touchpoint in one place",
                            "Understand your business with real, current data",
                        ].map((item, i) => (
                            <motion.div
                                key={item}
                                {...fadeUp(reduced)}
                                transition={{ ...fadeUp(reduced).transition, delay: (i % 3) * 0.06 }}
                                className="flex items-start gap-3 rounded-2xl border border-slate-200/80 p-5"
                            >
                                <span className="w-6 h-6 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
                                    ✓
                                </span>
                                <p className="text-sm font-medium text-slate-700 leading-relaxed">{item}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ================= TRUST / CONTROL ================= */}
            <section className="py-24 sm:py-28 bg-slate-50">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...fadeUp(reduced)} className="max-w-2xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Control, not blind autonomy</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-3">
                            Your AI Workforce acts on real data — and you stay in control.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-12">
                        {[
                            { icon: Eye, title: "Full visibility", body: "Every conversation, lead, and appointment is reviewable from your dashboard." },
                            { icon: Database, title: "Grounded in your data", body: "Answers come from your configured business information — never invented details." },
                            { icon: KeyRound, title: "Business-specific context", body: "Each business's data, conversations, and configuration stay isolated to that business." },
                            { icon: ShieldCheck, title: "Built-in safeguards", body: "Guardrails keep AI Workforce replies on-topic and resistant to manipulation attempts." },
                        ].map((item, i) => (
                            <motion.div
                                key={item.title}
                                {...fadeUp(reduced)}
                                transition={{ ...fadeUp(reduced).transition, delay: i * 0.05 }}
                                className="rounded-2xl bg-white border border-slate-200/80 shadow-soft p-6"
                            >
                                <div className="w-10 h-10 rounded-xl bg-ink-900 text-white flex items-center justify-center">
                                    <item.icon size={18} aria-hidden="true" />
                                </div>
                                <p className="font-semibold text-slate-900 mt-4">{item.title}</p>
                                <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{item.body}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ================= FINAL CTA ================= */}
            <section className="relative overflow-hidden bg-ink-900 py-24 sm:py-28">
                <div
                    className="absolute inset-0 pointer-events-none"
                    style={{ background: "radial-gradient(50% 60% at 50% 100%, rgba(139,59,255,0.25) 0%, rgba(5,6,13,0) 70%)" }}
                    aria-hidden="true"
                />
                <div className="relative max-w-3xl mx-auto px-5 sm:px-8 text-center">
                    <motion.h2 {...fadeUp(reduced)} className="font-display text-3xl sm:text-5xl font-bold tracking-tight text-white">
                        Build your AI Workforce.
                    </motion.h2>
                    <motion.p
                        {...fadeUp(reduced)}
                        transition={{ ...fadeUp(reduced).transition, delay: 0.05 }}
                        className="text-slate-300 mt-4 text-lg"
                    >
                        Free to start. No credit card required.
                    </motion.p>
                    <motion.div
                        {...fadeUp(reduced)}
                        transition={{ ...fadeUp(reduced).transition, delay: 0.1 }}
                        className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-8"
                    >
                        <Link to="/register" className="w-full sm:w-auto">
                            <Button size="lg" className="w-full sm:w-auto">
                                Start Free <ArrowRight size={18} />
                            </Button>
                        </Link>
                        <Link to="/login" className="w-full sm:w-auto">
                            <Button size="lg" variant="secondary" className="w-full sm:w-auto !bg-white/[0.06] !text-white !border-white/15 hover:!bg-white/10">
                                Sign In
                            </Button>
                        </Link>
                    </motion.div>
                </div>
            </section>

            {/* ================= FOOTER ================= */}
            <footer className="bg-white border-t border-slate-200/80 py-14">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-8">
                        <Logo size="sm" />
                        <nav aria-label="Footer" className="flex flex-wrap gap-x-8 gap-y-3">
                            {NAV_LINKS.map((link) => (
                                <a key={link.href} href={link.href} className="text-sm text-slate-500 hover:text-ink-900 transition-colors">
                                    {link.label}
                                </a>
                            ))}
                            <Link to="/login" className="text-sm text-slate-500 hover:text-ink-900 transition-colors">
                                Sign In
                            </Link>
                        </nav>
                    </div>
                    <div className="border-t border-slate-100 mt-8 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
                        <p className="text-xs text-slate-400">© {new Date().getFullYear()} AIFlow. All rights reserved.</p>
                    </div>
                </div>
            </footer>
        </div>
    );
}
