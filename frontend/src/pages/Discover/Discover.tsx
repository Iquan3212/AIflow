import { Link } from "react-router-dom";
import { ArrowRight, Bot, BookOpen, MessageSquare, ShieldCheck } from "lucide-react";

import Logo from "../../components/brand/Logo";
import Button from "../../components/ui/Button";

/** The buyer-facing entry point linked from the landing page's "Explore
 * Properties" CTA. Honest about where the product actually is: no
 * cross-agency property search/listing API exists yet (see
 * BuyerHome.tsx), so this introduces the real, working piece — a free
 * buyer account plus each agency's own AI assistant — rather than a
 * fabricated marketplace grid. */
export default function Discover() {
    return (
        <div className="min-h-screen bg-stone-50">
            <header className="border-b border-slate-200/70 bg-white/80 backdrop-blur-xl sticky top-0 z-10">
                <div className="max-w-5xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
                    <Link to="/" aria-label="AIFlow home">
                        <Logo size="sm" />
                    </Link>
                    <div className="flex items-center gap-2">
                        <Link to="/buyer/login" className="text-sm font-semibold text-slate-700 hover:text-ink-950 px-3.5 py-2">
                            Sign in
                        </Link>
                        <Link to="/buyer/register">
                            <Button size="sm" variant="flare">Create account</Button>
                        </Link>
                    </div>
                </div>
            </header>

            <main className="max-w-3xl mx-auto px-5 sm:px-8 py-20">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">For buyers</p>
                <h1 className="font-display text-4xl sm:text-5xl font-medium tracking-tight text-ink-950 mt-4 leading-[1.1]">
                    Property discovery,
                    <br />
                    powered by each agency's AI.
                </h1>
                <p className="text-lg text-slate-500 mt-6 max-w-xl leading-relaxed">
                    A single search across every agency on AIFlow is on the roadmap and
                    isn't live yet. What's real today: a free buyer account, and every
                    participating agency's own AI assistant — grounded in their real
                    listings, pricing, and policies, never a guess.
                </p>

                <div className="flex flex-wrap items-center gap-3 mt-9">
                    <Link to="/buyer/register">
                        <Button size="lg" variant="flare">
                            Create a free account <ArrowRight size={18} />
                        </Button>
                    </Link>
                    <Link to="/buyer/login">
                        <Button size="lg" variant="secondary">Sign in</Button>
                    </Link>
                </div>

                <div className="grid sm:grid-cols-3 gap-4 mt-16">
                    <div className="rounded-2xl bg-white border border-slate-200/80 p-5">
                        <MessageSquare size={18} className="text-brand-600" aria-hidden="true" />
                        <p className="text-sm font-semibold text-ink-950 mt-3">Ask a real question</p>
                        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">Message an agency's AI assistant about a specific project or price.</p>
                    </div>
                    <div className="rounded-2xl bg-white border border-slate-200/80 p-5">
                        <BookOpen size={18} className="text-brand-600" aria-hidden="true" />
                        <p className="text-sm font-semibold text-ink-950 mt-3">Grounded in real listings</p>
                        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">Answers come from the agency's own Knowledge Base — never invented.</p>
                    </div>
                    <div className="rounded-2xl bg-white border border-slate-200/80 p-5">
                        <ShieldCheck size={18} className="text-brand-600" aria-hidden="true" />
                        <p className="text-sm font-semibold text-ink-950 mt-3">Your account, everywhere</p>
                        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">One buyer account, kept separate from any agency you talk to.</p>
                    </div>
                </div>

                <div className="mt-16 rounded-3xl bg-ink-950 text-white p-8 flex items-center gap-5">
                    <div className="w-12 h-12 rounded-xl bg-white/10 text-flare-400 flex items-center justify-center shrink-0">
                        <Bot size={22} aria-hidden="true" />
                    </div>
                    <div>
                        <p className="font-display font-medium">Run an agency instead?</p>
                        <p className="text-sm text-slate-400 mt-1">
                            Set up your own AI Workforce and start turning inquiries into site visits.{" "}
                            <Link to="/register" className="text-flare-400 font-semibold hover:text-flare-300">
                                Get started →
                            </Link>
                        </p>
                    </div>
                </div>
            </main>
        </div>
    );
}
