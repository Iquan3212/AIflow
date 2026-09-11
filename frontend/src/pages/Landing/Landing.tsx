import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
    ArrowRight,
    ArrowUpRight,
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
    Bot,
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

const EASE = "easeOut" as const;

function reveal(reduced: boolean | null, delay = 0) {
    if (reduced) return {};
    return {
        initial: { opacity: 0, y: 16 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, margin: "-60px" },
        transition: { duration: 0.55, ease: EASE, delay },
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
        <div className="bg-white text-ink-950 overflow-x-clip">
            {/* ================= FLOATING NAVBAR ================= */}
            <div className="fixed top-4 inset-x-0 z-50 px-4 sm:px-6 flex justify-center">
                <header
                    className={`w-full max-w-6xl rounded-2xl transition-all duration-300 ${
                        scrolled
                            ? "bg-white/90 backdrop-blur-md shadow-lifted border border-slate-200/70"
                            : "bg-white/40 backdrop-blur-sm border border-white/40"
                    }`}
                >
                    <div className="h-14 px-4 sm:px-5 flex items-center justify-between">
                        <Link to="/" aria-label="AIFlow home">
                            <Logo size="sm" />
                        </Link>

                        <nav aria-label="Primary" className="hidden md:flex items-center gap-1">
                            {NAV_LINKS.map((link) => (
                                <a
                                    key={link.href}
                                    href={link.href}
                                    className="text-sm font-medium text-slate-600 hover:text-ink-950 hover:bg-ink-950/5 rounded-full px-3.5 py-2 transition-colors"
                                >
                                    {link.label}
                                </a>
                            ))}
                        </nav>

                        <div className="hidden md:flex items-center gap-2">
                            <Link to="/login" className="text-sm font-semibold text-slate-700 hover:text-ink-950 px-3.5 py-2 transition-colors">
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
                            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
                        </button>
                    </div>

                    {mobileOpen && (
                        <div className="md:hidden border-t border-slate-200/70 px-4 py-3 flex flex-col gap-1">
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
            </div>

            {/* ================= HERO — asymmetric, not centered/stacked ================= */}
            <section className="relative bg-ink-950 pt-36 pb-28 sm:pt-44 sm:pb-40">
                <div className="absolute inset-0 bg-dot-grid opacity-60" aria-hidden="true" />
                <div
                    className="absolute inset-0 pointer-events-none"
                    style={{ background: "radial-gradient(55% 45% at 15% 15%, rgba(139,59,255,0.35) 0%, rgba(5,6,13,0) 65%)" }}
                    aria-hidden="true"
                />

                <div className="relative max-w-7xl mx-auto px-5 sm:px-8 grid lg:grid-cols-[1.05fr_0.95fr] gap-14 lg:gap-8 items-center">
                    <div>
                        <motion.span
                            {...reveal(reduced)}
                            className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.06] border border-white/10 px-3.5 py-1.5 text-xs font-medium text-slate-300"
                        >
                            <span className="w-1.5 h-1.5 rounded-full bg-flare-500" />
                            An AI Workforce for growing agencies
                        </motion.span>

                        <motion.h1
                            {...reveal(reduced, 0.05)}
                            className="font-display text-5xl sm:text-6xl xl:text-[4.5rem] font-semibold tracking-tight text-white mt-7 leading-[1.02]"
                        >
                            Your agency,
                            <br />
                            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-300 via-brand-200 to-white">
                                run by an AI Workforce.
                            </span>
                        </motion.h1>

                        <motion.p
                            {...reveal(reduced, 0.1)}
                            className="text-lg text-slate-400 mt-7 max-w-lg leading-relaxed"
                        >
                            Not one generic chatbot — a coordinated team of specialized AI employees
                            handling conversations, leads, appointments, support and analytics.
                        </motion.p>

                        <motion.div {...reveal(reduced, 0.15)} className="flex flex-wrap items-center gap-3 mt-10">
                            <Link to="/register">
                                <Button size="lg">
                                    Start Free <ArrowRight size={18} />
                                </Button>
                            </Link>
                            <a href="#how-it-works">
                                <Button size="lg" variant="secondary" className="!bg-white/[0.06] !text-white !border-white/15 hover:!border-white/30">
                                    See How It Works
                                </Button>
                            </a>
                        </motion.div>

                        <motion.div {...reveal(reduced, 0.2)} className="flex items-center gap-6 mt-14 text-slate-500 text-xs font-medium">
                            <span>No credit card required</span>
                            <span className="w-1 h-1 rounded-full bg-slate-700" />
                            <span>Free to start</span>
                        </motion.div>
                    </div>

                    {/* Floating "workforce window" card - a real coded diagram, tilted for
                        depth, not a fabricated product screenshot */}
                    <motion.div
                        {...reveal(reduced, 0.15)}
                        className="relative lg:justify-self-end w-full max-w-md lg:rotate-2"
                    >
                        <div className="absolute -inset-6 bg-brand-500/20 blur-3xl rounded-full" aria-hidden="true" />
                        <div className="relative bg-ink-900 border border-white/10 rounded-3xl shadow-lifted p-5 sm:p-6">
                            <div className="flex items-center gap-1.5 mb-5">
                                <span className="w-2.5 h-2.5 rounded-full bg-white/15" />
                                <span className="w-2.5 h-2.5 rounded-full bg-white/15" />
                                <span className="w-2.5 h-2.5 rounded-full bg-white/15" />
                            </div>
                            <div className="flex flex-col items-center">
                                <div className="inline-flex items-center gap-2 rounded-xl bg-white text-ink-950 px-4 py-2.5 shadow-glow">
                                    <Bot size={17} className="text-brand-600" aria-hidden="true" />
                                    <span className="font-display font-semibold text-sm">Manager AI</span>
                                </div>
                                <div className="h-6 w-px bg-white/15 my-1" aria-hidden="true" />
                                <div className="grid grid-cols-3 gap-2 w-full">
                                    {["Sales", "Reception", "Support", "Finance", "Analytics", "Marketing"].map((role) => (
                                        <div
                                            key={role}
                                            className="rounded-lg bg-white/[0.05] border border-white/10 py-2.5 text-center text-[11px] font-medium text-slate-300"
                                        >
                                            {role}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* ================= PROBLEM — bento, not a uniform 4-col grid ================= */}
            <section className="py-24 sm:py-32 bg-white">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.p {...reveal(reduced)} className="text-xs font-semibold uppercase tracking-wide text-brand-600">
                        The problem
                    </motion.p>

                    <div className="grid lg:grid-cols-3 gap-5 mt-6">
                        <motion.div
                            {...reveal(reduced, 0.05)}
                            className="lg:col-span-2 lg:row-span-2 rounded-3xl bg-ink-950 text-white p-8 sm:p-10 flex flex-col justify-between"
                        >
                            <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight leading-tight">
                                Running an agency means operations pile up faster than your team can keep up.
                            </h2>
                            <p className="text-slate-400 text-sm mt-8 max-w-md">
                                A slow reply is often the difference between a customer and a missed sale — and
                                every channel your customers use adds one more inbox to watch.
                            </p>
                        </motion.div>

                        {[
                            { title: "Leads go cold", body: "Silence loses sales." },
                            { title: "Customers wait", body: "Messages pile up after hours." },
                            { title: "Scheduling is manual", body: "No single source of truth." },
                            { title: "Data lives everywhere", body: "Scattered across tools." },
                        ].map((item, i) => (
                            <motion.div
                                key={item.title}
                                {...reveal(reduced, 0.1 + i * 0.05)}
                                className="rounded-3xl border border-slate-200/80 p-6 flex flex-col justify-between"
                            >
                                <p className="font-display font-semibold text-ink-950">{item.title}</p>
                                <p className="text-sm text-slate-500 mt-3">{item.body}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ================= AI WORKFORCE — text beside a floating diagram window ================= */}
            <section id="workforce" className="py-24 sm:py-32 bg-slate-50 scroll-mt-24">
                <div className="max-w-7xl mx-auto px-5 sm:px-8">
                    <div className="grid lg:grid-cols-[0.85fr_1.15fr] gap-14 items-center">
                        <motion.div {...reveal(reduced)}>
                            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">The AI Workforce</p>
                            <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight mt-4 leading-tight">
                                One Manager. Six specialists.
                            </h2>
                            <p className="text-slate-500 mt-5 leading-relaxed">
                                A Manager AI reads every conversation, decides which specialist should handle
                                it, and coordinates the reply — so customers always get a focused answer
                                instead of a generic one.
                            </p>
                            <a href="#features" className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-600 hover:text-brand-700 mt-7">
                                Explore what each role does <ArrowUpRight size={15} />
                            </a>
                        </motion.div>

                        <motion.div {...reveal(reduced, 0.1)}>
                            <WorkforceDiagram variant="light" />
                        </motion.div>
                    </div>
                </div>
            </section>

            {/* ================= HOW IT WORKS — stepped timeline ================= */}
            <section id="how-it-works" className="py-24 sm:py-32 bg-white scroll-mt-24">
                <div className="max-w-5xl mx-auto px-5 sm:px-8">
                    <motion.div {...reveal(reduced)} className="max-w-xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">How it works</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight mt-4">
                            Set up your AI Workforce in minutes.
                        </h2>
                    </motion.div>

                    <div className="relative mt-16">
                        <div className="hidden sm:block absolute top-6 left-0 right-0 h-px bg-slate-200" aria-hidden="true" />
                        <div className="grid sm:grid-cols-4 gap-10 sm:gap-6">
                            {[
                                { title: "Connect your agency", body: "Sign up and tell AIFlow about your services, tone, and hours." },
                                { title: "Configure your Workforce", body: "Manager AI is ready immediately, grounded in your data." },
                                { title: "Connect your channels", body: "Bring in website chat, WhatsApp, and Instagram as needed." },
                                { title: "Stay in control", body: "Review conversations and leads — the AI never acts unsupervised." },
                            ].map((item, i) => (
                                <motion.div key={item.title} {...reveal(reduced, i * 0.07)} className="relative">
                                    <div className="w-12 h-12 rounded-full bg-ink-950 text-white font-display font-semibold flex items-center justify-center text-sm relative z-10">
                                        {i + 1}
                                    </div>
                                    <p className="font-display font-semibold text-ink-950 mt-4">{item.title}</p>
                                    <p className="text-sm text-slate-500 mt-2 leading-relaxed">{item.body}</p>
                                </motion.div>
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            {/* ================= FEATURES — bento grid, mixed sizes ================= */}
            <section id="features" className="py-24 sm:py-32 bg-slate-50 scroll-mt-24">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...reveal(reduced)} className="max-w-xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">What's included</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight mt-4">
                            Everything your AI Workforce needs to get real work done.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 lg:grid-rows-2 gap-5 mt-12">
                        <motion.div
                            {...reveal(reduced, 0.05)}
                            className="lg:col-span-2 lg:row-span-2 rounded-3xl bg-ink-950 text-white p-8 flex flex-col justify-between"
                        >
                            <div className="w-11 h-11 rounded-xl bg-white/10 text-brand-300 flex items-center justify-center">
                                <MessageSquare size={20} aria-hidden="true" />
                            </div>
                            <div>
                                <p className="font-display text-xl font-semibold">Customer conversations</p>
                                <p className="text-sm text-slate-400 mt-2 leading-relaxed max-w-xs">
                                    Every message — from any channel — lands in one unified conversation
                                    history your whole team can see.
                                </p>
                            </div>
                        </motion.div>

                        {[
                            { icon: Users, title: "Lead management", body: "Sales AI captures interest as real, reviewable leads." },
                            { icon: CalendarClock, title: "Appointments", body: "Real availability checks before booking or rescheduling." },
                            { icon: LifeBuoy, title: "Support tickets", body: "Every issue logged as a trackable ticket." },
                            { icon: FileText, title: "AI-drafted content", body: "Quotations and campaign copy, ready to review." },
                            { icon: BarChart3, title: "Agency analytics", body: "Ask about your real leads and activity, in plain language." },
                        ].map((item, i) => (
                            <motion.div
                                key={item.title}
                                {...reveal(reduced, 0.1 + i * 0.05)}
                                className="rounded-3xl bg-white border border-slate-200/80 p-6 hover:border-slate-300 transition-colors duration-200"
                            >
                                <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
                                    <item.icon size={18} aria-hidden="true" />
                                </div>
                                <p className="font-semibold text-ink-950 mt-4">{item.title}</p>
                                <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{item.body}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ================= CHANNELS ================= */}
            <section id="channels" className="py-24 sm:py-32 bg-ink-950 text-white scroll-mt-24 relative overflow-hidden">
                <div className="absolute inset-0 bg-dot-grid opacity-40" aria-hidden="true" />
                <div className="relative max-w-5xl mx-auto px-5 sm:px-8">
                    <div className="grid lg:grid-cols-2 gap-14 items-center">
                        <motion.div {...reveal(reduced)}>
                            <p className="text-xs font-semibold uppercase tracking-wide text-brand-300">Multi-channel, one conversation</p>
                            <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight mt-4 leading-tight">
                                Wherever a customer reaches out, your Workforce is there.
                            </h2>
                            <p className="text-slate-400 mt-5 leading-relaxed max-w-md">
                                Website chat, WhatsApp, and Instagram all feed into the same conversation and
                                the same Manager AI — context is never lost between channels.
                            </p>
                        </motion.div>

                        <motion.div {...reveal(reduced, 0.1)} className="flex flex-col items-center gap-3">
                            <div className="flex flex-wrap items-center justify-center gap-2.5">
                                {["Website", "WhatsApp", "Instagram"].map((ch) => (
                                    <span
                                        key={ch}
                                        className="inline-flex items-center gap-2 rounded-full bg-white/[0.06] border border-white/10 px-4 py-2 text-sm font-medium"
                                    >
                                        <Globe size={14} className="text-brand-300" aria-hidden="true" />
                                        {ch}
                                    </span>
                                ))}
                            </div>
                            <div className="h-7 w-px bg-white/15" aria-hidden="true" />
                            <div className="inline-flex items-center gap-2 rounded-full bg-brand-500/15 border border-brand-400/30 px-4 py-2 text-sm font-medium text-brand-200">
                                Unified conversation
                            </div>
                            <div className="h-7 w-px bg-white/15" aria-hidden="true" />
                            <div className="inline-flex items-center gap-2.5 rounded-2xl bg-white text-ink-950 px-5 py-3 shadow-glow font-display font-semibold text-sm">
                                <Bot size={16} className="text-brand-600" aria-hidden="true" />
                                Manager AI
                            </div>
                        </motion.div>
                    </div>
                </div>
            </section>

            {/* ================= BENEFITS — checklist + stat panel, not uniform cards ================= */}
            <section className="py-24 sm:py-32 bg-white">
                <div className="max-w-6xl mx-auto px-5 sm:px-8 grid lg:grid-cols-[1fr_0.8fr] gap-14 items-start">
                    <motion.div {...reveal(reduced)}>
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Why it matters</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight mt-4 mb-9">
                            Built around agency outcomes, not technology.
                        </h2>

                        <ul className="space-y-4">
                            {[
                                "Respond to customers faster, around the clock",
                                "Capture more leads instead of losing them to silence",
                                "Reduce repetitive work for your team",
                                "Never miss a follow-up",
                                "Coordinate every customer touchpoint in one place",
                                "Understand your agency with real, current data",
                            ].map((item, i) => (
                                <motion.li
                                    key={item}
                                    {...reveal(reduced, i * 0.04)}
                                    className="flex items-start gap-3 pb-4 border-b border-slate-100 last:border-0"
                                >
                                    <span className="w-6 h-6 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
                                        ✓
                                    </span>
                                    <p className="text-[15px] font-medium text-slate-700">{item}</p>
                                </motion.li>
                            ))}
                        </ul>
                    </motion.div>

                    <motion.div {...reveal(reduced, 0.1)} className="rounded-3xl bg-flare-500 p-8 sm:p-10 sticky top-24">
                        <p className="font-display text-5xl font-semibold text-ink-950 tracking-tight">7</p>
                        <p className="text-ink-950/80 font-medium mt-1">specialized AI employees, coordinated by one Manager</p>
                        <div className="h-px bg-ink-950/15 my-6" />
                        <p className="font-display text-5xl font-semibold text-ink-950 tracking-tight">3</p>
                        <p className="text-ink-950/80 font-medium mt-1">channels feeding one unified conversation</p>
                        <div className="h-px bg-ink-950/15 my-6" />
                        <p className="font-display text-5xl font-semibold text-ink-950 tracking-tight">1</p>
                        <p className="text-ink-950/80 font-medium mt-1">dashboard to see and control it all</p>
                    </motion.div>
                </div>
            </section>

            {/* ================= TRUST / CONTROL — bento ================= */}
            <section className="py-24 sm:py-32 bg-slate-50">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...reveal(reduced)} className="max-w-xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Control, not blind autonomy</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight mt-4">
                            Your AI Workforce acts on real data — and you stay in control.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 gap-5 mt-12">
                        {[
                            { icon: Eye, title: "Full visibility", body: "Every conversation, lead, and appointment is reviewable from your dashboard." },
                            { icon: Database, title: "Grounded in your data", body: "Answers come from your configured agency information — never invented details." },
                            { icon: KeyRound, title: "Agency-specific context", body: "Each agency's data, conversations, and configuration stay isolated to that agency." },
                            { icon: ShieldCheck, title: "Built-in safeguards", body: "Guardrails keep AI Workforce replies on-topic and resistant to manipulation attempts." },
                        ].map((item, i) => (
                            <motion.div
                                key={item.title}
                                {...reveal(reduced, i * 0.06)}
                                className="rounded-3xl bg-white border border-slate-200/80 p-7 flex items-start gap-5"
                            >
                                <div className="w-11 h-11 rounded-xl bg-ink-950 text-white flex items-center justify-center shrink-0">
                                    <item.icon size={19} aria-hidden="true" />
                                </div>
                                <div>
                                    <p className="font-semibold text-ink-950">{item.title}</p>
                                    <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{item.body}</p>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ================= FINAL CTA ================= */}
            <section className="relative overflow-hidden bg-ink-950 py-28 sm:py-36">
                <div className="absolute inset-0 bg-dot-grid opacity-50" aria-hidden="true" />
                <div
                    className="absolute inset-0 pointer-events-none"
                    style={{ background: "radial-gradient(50% 60% at 50% 100%, rgba(139,59,255,0.3) 0%, rgba(5,6,13,0) 70%)" }}
                    aria-hidden="true"
                />
                <div className="relative max-w-3xl mx-auto px-5 sm:px-8 text-center">
                    <motion.h2 {...reveal(reduced)} className="font-display text-4xl sm:text-6xl font-semibold tracking-tight text-white">
                        Build your AI Workforce.
                    </motion.h2>
                    <motion.p {...reveal(reduced, 0.05)} className="text-slate-400 mt-5 text-lg">
                        Free to start. No credit card required.
                    </motion.p>
                    <motion.div {...reveal(reduced, 0.1)} className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-9">
                        <Link to="/register" className="w-full sm:w-auto">
                            <Button size="lg" variant="flare" className="w-full sm:w-auto">
                                Start Free <ArrowRight size={18} />
                            </Button>
                        </Link>
                        <Link to="/login" className="w-full sm:w-auto">
                            <Button size="lg" variant="secondary" className="w-full sm:w-auto !bg-white/[0.06] !text-white !border-white/15 hover:!border-white/30">
                                Sign In
                            </Button>
                        </Link>
                    </motion.div>
                </div>
            </section>

            {/* ================= FOOTER ================= */}
            <footer className="bg-white border-t border-slate-200/80 pt-16 pb-10">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-10">
                        <div className="lg:col-span-2">
                            <Logo size="sm" />
                            <p className="text-sm text-slate-500 mt-4 max-w-xs leading-relaxed">
                                An AI Workforce for growing agencies — coordinated conversations, leads,
                                appointments, support and analytics.
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">Product</p>
                            <ul className="space-y-2.5">
                                {NAV_LINKS.map((link) => (
                                    <li key={link.href}>
                                        <a href={link.href} className="text-sm text-slate-600 hover:text-ink-950 transition-colors">
                                            {link.label}
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">Account</p>
                            <ul className="space-y-2.5">
                                <li>
                                    <Link to="/login" className="text-sm text-slate-600 hover:text-ink-950 transition-colors">
                                        Sign In
                                    </Link>
                                </li>
                                <li>
                                    <Link to="/register" className="text-sm text-slate-600 hover:text-ink-950 transition-colors">
                                        Start Free
                                    </Link>
                                </li>
                            </ul>
                        </div>
                    </div>
                    <div className="border-t border-slate-100 mt-12 pt-6">
                        <p className="text-xs text-slate-400">© {new Date().getFullYear()} AIFlow. All rights reserved.</p>
                    </div>
                </div>
            </footer>
        </div>
    );
}
