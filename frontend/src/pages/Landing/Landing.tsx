import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
    ArrowRight,
    ArrowUpRight,
    MessageSquare,
    Users,
    CalendarClock,
    BarChart3,
    Globe,
    ShieldCheck,
    KeyRound,
    Database,
    Eye,
    Menu,
    X,
    Bot,
    BookOpen,
    Workflow,
    Building2,
} from "lucide-react";

import Logo from "../../components/brand/Logo";
import WorkforceDiagram from "../../components/brand/WorkforceDiagram";
import Button from "../../components/ui/Button";

const NAV_LINKS = [
    { href: "#discovery", label: "Property Discovery" },
    { href: "#workforce", label: "AI Workforce" },
    { href: "#operations", label: "Operations" },
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
                                    className="text-sm font-medium text-slate-600 hover:text-ink-950 hover:bg-ink-950/5 rounded-lg px-3.5 py-2 transition-colors"
                                >
                                    {link.label}
                                </a>
                            ))}
                        </nav>

                        <div className="hidden md:flex items-center gap-2">
                            <Link to="/login" className="text-sm font-semibold text-slate-700 hover:text-ink-950 px-3.5 py-2 transition-colors">
                                Agency Sign In
                            </Link>
                            <Link to="/register">
                                <Button size="sm">For Agencies</Button>
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
                                    <Button variant="secondary" className="w-full">Agency Sign In</Button>
                                </Link>
                                <Link to="/register" onClick={() => setMobileOpen(false)}>
                                    <Button className="w-full">For Agencies</Button>
                                </Link>
                            </div>
                        </div>
                    )}
                </header>
            </div>

            {/* ================= HERO ================= */}
            <section className="relative bg-ink-950 pt-36 pb-28 sm:pt-44 sm:pb-40">
                <div className="absolute inset-0 bg-dot-grid opacity-60" aria-hidden="true" />
                <div
                    className="absolute inset-0 pointer-events-none"
                    style={{ background: "radial-gradient(55% 45% at 15% 15%, rgba(42,82,64,0.55) 0%, rgba(15,18,15,0) 65%)" }}
                    aria-hidden="true"
                />

                <div className="relative max-w-7xl mx-auto px-5 sm:px-8 grid lg:grid-cols-[1.05fr_0.95fr] gap-14 lg:gap-8 items-center">
                    <div>
                        <motion.span
                            {...reveal(reduced)}
                            className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.06] border border-white/10 px-3.5 py-1.5 text-xs font-medium text-slate-300"
                        >
                            <span className="w-1.5 h-1.5 rounded-full bg-flare-500" />
                            An AI-powered real estate marketplace + agency OS
                        </motion.span>

                        <motion.h1
                            {...reveal(reduced, 0.05)}
                            className="font-display text-5xl sm:text-6xl xl:text-[4.4rem] font-medium tracking-tight text-white mt-7 leading-[1.05]"
                        >
                            Where properties
                            <br />
                            meet intelligence.
                        </motion.h1>

                        <motion.p
                            {...reveal(reduced, 0.1)}
                            className="text-lg text-slate-400 mt-7 max-w-lg leading-relaxed"
                        >
                            Discover properties with AI. Help agencies convert inquiries into
                            site visits and bookings — one coordinated Workforce, grounded in your
                            own listings and data.
                        </motion.p>

                        <motion.div {...reveal(reduced, 0.15)} className="flex flex-wrap items-center gap-3 mt-10">
                            <Link to="/discover">
                                <Button size="lg" variant="flare">
                                    Explore Properties <ArrowRight size={18} />
                                </Button>
                            </Link>
                            <Link to="/register">
                                <Button size="lg" variant="secondary" className="!bg-white/[0.06] !text-white !border-white/15 hover:!border-white/30">
                                    For Agencies
                                </Button>
                            </Link>
                        </motion.div>

                        <motion.div {...reveal(reduced, 0.2)} className="flex items-center gap-6 mt-14 text-slate-500 text-xs font-medium">
                            <span>Buyer accounts are free</span>
                            <span className="w-1 h-1 rounded-full bg-slate-700" />
                            <span>No credit card required for agencies</span>
                        </motion.div>
                    </div>

                    {/* Floating "workforce window" card - a real coded diagram, tilted for
                        depth, not a fabricated product screenshot */}
                    <motion.div
                        {...reveal(reduced, 0.15)}
                        className="relative lg:justify-self-end w-full max-w-md lg:rotate-2 tilt-stage"
                    >
                        <div className="absolute -inset-6 bg-brand-500/25 blur-3xl rounded-full" aria-hidden="true" />
                        <div className="relative bg-ink-900 border border-white/10 rounded-3xl shadow-lifted p-5 sm:p-6 tilt-card">
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

            {/* ================= AI PROPERTY DISCOVERY ================= */}
            <section id="discovery" className="py-24 sm:py-32 bg-white scroll-mt-24">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <div className="grid lg:grid-cols-[0.9fr_1.1fr] gap-14 items-center">
                        <motion.div {...reveal(reduced)}>
                            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">AI property discovery</p>
                            <h2 className="font-display text-3xl sm:text-4xl font-medium tracking-tight mt-4 leading-tight">
                                Ask a question, get an answer grounded in the agency's own listings.
                            </h2>
                            <p className="text-slate-500 mt-5 leading-relaxed">
                                Every buyer conversation is answered from the agency's real Knowledge
                                Base — project details, pricing, RERA information, refund policy —
                                never a fabricated fact or an invented price.
                            </p>
                            <a href="#workforce" className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-600 hover:text-brand-700 mt-7">
                                See how the Workforce handles it <ArrowUpRight size={15} />
                            </a>
                        </motion.div>

                        <motion.div {...reveal(reduced, 0.1)} className="rounded-3xl bg-stone-100 border border-slate-200/80 p-6 sm:p-8">
                            <div className="flex justify-end mb-3">
                                <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand-600 text-white px-4 py-2.5 text-sm">
                                    Do you have a 3BHK under 1.5 crore in Whitefield?
                                </div>
                            </div>
                            <div className="flex justify-start">
                                <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-white border border-slate-200 px-4 py-3 text-sm text-ink-950 shadow-soft">
                                    <p>Yes — Unit U-SR-1203 at Skyline Residences is a 3BHK, 1,450 sq.ft,
                                    available at ₹1,45,00,000. Would you like to schedule a site visit?</p>
                                    <p className="text-[11px] text-slate-400 mt-2 flex items-center gap-1.5">
                                        <BookOpen size={12} aria-hidden="true" /> Sourced from Project_Overview.txt
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                </div>
            </section>

            {/* ================= AI WORKFORCE ================= */}
            <section id="workforce" className="py-24 sm:py-32 bg-slate-50 scroll-mt-24">
                <div className="max-w-7xl mx-auto px-5 sm:px-8">
                    <div className="grid lg:grid-cols-[0.85fr_1.15fr] gap-14 items-center">
                        <motion.div {...reveal(reduced)}>
                            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">The agency AI Workforce</p>
                            <h2 className="font-display text-3xl sm:text-4xl font-medium tracking-tight mt-4 leading-tight">
                                One Manager. Six specialists. Every inquiry, handled.
                            </h2>
                            <p className="text-slate-500 mt-5 leading-relaxed">
                                A Manager AI reads every conversation, decides which specialist should
                                handle it, and coordinates the reply — turning a buyer's first question
                                into a qualified lead, then a scheduled site visit.
                            </p>
                            <a href="#operations" className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-600 hover:text-brand-700 mt-7">
                                See the operating system behind it <ArrowUpRight size={15} />
                            </a>
                        </motion.div>

                        <motion.div {...reveal(reduced, 0.1)}>
                            <WorkforceDiagram variant="light" />
                        </motion.div>
                    </div>
                </div>
            </section>

            {/* ================= OPERATIONS — bento grid ================= */}
            <section id="operations" className="py-24 sm:py-32 bg-white scroll-mt-24">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...reveal(reduced)} className="max-w-xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">The agency operating system</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-medium tracking-tight mt-4">
                            From first message to a booked site visit.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 lg:grid-rows-2 gap-5 mt-12">
                        <motion.div
                            {...reveal(reduced, 0.05)}
                            className="lg:col-span-2 lg:row-span-2 rounded-3xl bg-ink-950 text-white p-8 flex flex-col justify-between"
                        >
                            <div className="w-11 h-11 rounded-xl bg-white/10 text-flare-400 flex items-center justify-center">
                                <MessageSquare size={20} aria-hidden="true" />
                            </div>
                            <div>
                                <p className="font-display text-xl font-medium">Lead conversion</p>
                                <p className="text-sm text-slate-400 mt-2 leading-relaxed max-w-xs">
                                    Every real buyer inquiry — name, budget, property preference — is
                                    captured as a genuine, reviewable lead your team can see and act on.
                                </p>
                            </div>
                        </motion.div>

                        {[
                            { icon: CalendarClock, title: "Site visits", body: "Real availability checks before scheduling, rescheduling, or cancelling a visit." },
                            { icon: Workflow, title: "Controlled workflows", body: "Automations that fire on real events — a new lead, a booked visit — with owner approval where it matters." },
                            { icon: Users, title: "Buyer profiles", body: "Preferences, conversations, and visit history in one place." },
                            { icon: BarChart3, title: "Agency analytics", body: "Ask about your real leads, visits, and activity, in plain language." },
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
                            <h2 className="font-display text-3xl sm:text-4xl font-medium tracking-tight mt-4 leading-tight">
                                Wherever a buyer reaches out, your Workforce is there.
                            </h2>
                            <p className="text-slate-400 mt-5 leading-relaxed max-w-md">
                                Website chat, WhatsApp, and Instagram all feed into the same
                                conversation and the same Manager AI — and Gmail keeps the follow-up
                                email loop connected, with your approval before anything sends.
                            </p>
                        </motion.div>

                        <motion.div {...reveal(reduced, 0.1)} className="flex flex-col items-center gap-3">
                            <div className="flex flex-wrap items-center justify-center gap-2.5">
                                {["Website", "WhatsApp", "Instagram"].map((ch) => (
                                    <span
                                        key={ch}
                                        className="inline-flex items-center gap-2 rounded-full bg-white/[0.06] border border-white/10 px-4 py-2 text-sm font-medium"
                                    >
                                        <Globe size={14} className="text-flare-400" aria-hidden="true" />
                                        {ch}
                                    </span>
                                ))}
                            </div>
                            <div className="h-7 w-px bg-white/15" aria-hidden="true" />
                            <div className="inline-flex items-center gap-2 rounded-full bg-brand-500/20 border border-brand-400/30 px-4 py-2 text-sm font-medium text-brand-200">
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

            {/* ================= TRUST / CONTROL ================= */}
            <section className="py-24 sm:py-32 bg-slate-50">
                <div className="max-w-6xl mx-auto px-5 sm:px-8">
                    <motion.div {...reveal(reduced)} className="max-w-xl">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Control, not blind autonomy</p>
                        <h2 className="font-display text-3xl sm:text-4xl font-medium tracking-tight mt-4">
                            Your Workforce acts on real listings — and you stay in control.
                        </h2>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 gap-5 mt-12">
                        {[
                            { icon: Eye, title: "Full visibility", body: "Every conversation, lead, and site visit is reviewable from the agency dashboard." },
                            { icon: Database, title: "Grounded in your listings", body: "Answers come from your configured Knowledge Base — never invented prices or availability." },
                            { icon: KeyRound, title: "Agency-specific data", body: "Each agency's inventory, conversations, and configuration stay isolated to that agency." },
                            { icon: ShieldCheck, title: "Built-in safeguards", body: "Guardrails keep replies on-topic and resistant to manipulation attempts." },
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

            {/* ================= DUAL AUDIENCE CTA ================= */}
            <section className="relative overflow-hidden bg-ink-950 py-28 sm:py-36">
                <div className="absolute inset-0 bg-dot-grid opacity-50" aria-hidden="true" />
                <div
                    className="absolute inset-0 pointer-events-none"
                    style={{ background: "radial-gradient(50% 60% at 50% 100%, rgba(42,82,64,0.5) 0%, rgba(15,18,15,0) 70%)" }}
                    aria-hidden="true"
                />
                <div className="relative max-w-4xl mx-auto px-5 sm:px-8 text-center">
                    <motion.h2 {...reveal(reduced)} className="font-display text-4xl sm:text-6xl font-medium tracking-tight text-white">
                        Two sides. One platform.
                    </motion.h2>
                    <motion.p {...reveal(reduced, 0.05)} className="text-slate-400 mt-5 text-lg max-w-2xl mx-auto">
                        A free discovery experience for buyers, and a coordinated operating
                        system for agencies — grounded in the same real data either way.
                    </motion.p>
                    <motion.div {...reveal(reduced, 0.1)} className="grid sm:grid-cols-2 gap-4 mt-12 max-w-xl mx-auto">
                        <Link to="/discover" className="group rounded-2xl bg-white/[0.06] border border-white/15 hover:border-flare-400/50 p-6 text-left transition-colors">
                            <Building2 size={20} className="text-flare-400" aria-hidden="true" />
                            <p className="font-display font-medium text-white mt-3">I'm a buyer</p>
                            <p className="text-sm text-slate-400 mt-1">Explore properties</p>
                            <span className="inline-flex items-center gap-1 text-xs font-semibold text-flare-400 mt-3 group-hover:gap-1.5 transition-all">
                                Start browsing <ArrowRight size={13} />
                            </span>
                        </Link>
                        <Link to="/register" className="group rounded-2xl bg-white text-ink-950 p-6 text-left shadow-glow transition-transform hover:-translate-y-0.5">
                            <Bot size={20} className="text-brand-600" aria-hidden="true" />
                            <p className="font-display font-medium mt-3">I run an agency</p>
                            <p className="text-sm text-slate-600 mt-1">Set up your AI Workforce</p>
                            <span className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 mt-3 group-hover:gap-1.5 transition-all">
                                Start free <ArrowRight size={13} />
                            </span>
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
                                An AI-powered real estate marketplace and agency operating system —
                                property discovery for buyers, coordinated conversations, leads, site
                                visits and analytics for agencies.
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
                                    <Link to="/discover" className="text-sm text-slate-600 hover:text-ink-950 transition-colors">
                                        Buyer: Explore properties
                                    </Link>
                                </li>
                                <li>
                                    <Link to="/login" className="text-sm text-slate-600 hover:text-ink-950 transition-colors">
                                        Agency: Sign in
                                    </Link>
                                </li>
                                <li>
                                    <Link to="/register" className="text-sm text-slate-600 hover:text-ink-950 transition-colors">
                                        Agency: Start free
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
