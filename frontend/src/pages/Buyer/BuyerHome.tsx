import { useEffect, useState } from "react";
import { Bookmark, Compass, LayoutGrid, MonitorSmartphone, Sparkles } from "lucide-react";

import BuyerShell from "../../components/layout/BuyerShell";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listBuyerSessions, revokeBuyerSession, type BuyerSession } from "../../services/buyerAuth";

export default function BuyerHome() {
    const [sessions, setSessions] = useState<BuyerSession[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setSessions(await listBuyerSessions());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        load();
    }, []);

    async function handleRevoke(id: string) {
        try {
            await revokeBuyerSession(id);
            setSessions((current) => current?.filter((s) => s.id !== id) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    return (
        <BuyerShell>
            <div className="mb-9">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">Buyer account</p>
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Welcome back</h1>
                <p className="text-sm text-slate-500 mt-1.5 max-w-xl">
                    Your account is set up. Here's exactly what's live today, and what's still on the roadmap.
                </p>
            </div>

            <div className="grid lg:grid-cols-3 gap-5">
                <Card className="lg:col-span-2 p-7 bg-ink-950 text-white border-none">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <div className="w-11 h-11 rounded-xl bg-white/10 text-flare-400 flex items-center justify-center mb-4">
                                <Compass size={20} aria-hidden="true" />
                            </div>
                            <h2 className="font-display text-xl font-medium">Cross-agency property search is coming</h2>
                            <p className="text-sm text-slate-400 mt-2 max-w-md leading-relaxed">
                                A unified search across every agency on AIFlow — with AI-matched
                                recommendations — is on the roadmap and not live yet. Today, each
                                agency's AI assistant already answers real questions about their
                                own listings, grounded in that agency's Knowledge Base.
                            </p>
                        </div>
                        <Badge tone="flare" className="shrink-0">Roadmap</Badge>
                    </div>
                </Card>

                <Card className="p-7">
                    <div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center mb-4">
                        <Sparkles size={20} aria-hidden="true" />
                    </div>
                    <h2 className="font-semibold text-ink-950">Have an agency's link?</h2>
                    <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                        Ask them for their AIFlow chat widget or website — you can ask their AI
                        assistant about specific projects, pricing, and site visits right now.
                    </p>
                </Card>
            </div>

            <div className="grid lg:grid-cols-2 gap-5 mt-5">
                <Card className="p-7">
                    <div className="flex items-center gap-2 mb-1">
                        <Bookmark size={16} className="text-slate-400" aria-hidden="true" />
                        <h2 className="text-sm font-semibold text-slate-700">Saved properties</h2>
                    </div>
                    <EmptyState
                        icon={<LayoutGrid size={26} />}
                        title="Not available yet"
                        description="Saving properties requires the property marketplace, which hasn't shipped yet — this is a real, honest placeholder, not missing data."
                    />
                </Card>

                <Card className="p-7">
                    <div className="flex items-center gap-2 mb-4">
                        <MonitorSmartphone size={16} className="text-slate-400" aria-hidden="true" />
                        <h2 className="text-sm font-semibold text-slate-700">Signed-in devices</h2>
                    </div>

                    {!sessions && !error && <LoadingState label="Loading sessions…" />}
                    {error && <ErrorState message={error} onRetry={load} />}
                    {sessions && !error && sessions.length === 0 && (
                        <EmptyState title="No other sessions" description="This device is the only one signed in." />
                    )}
                    {sessions && !error && sessions.length > 0 && (
                        <ul className="divide-y divide-slate-100">
                            {sessions.map((s) => (
                                <li key={s.id} className="py-3 flex items-center justify-between gap-3">
                                    <div className="min-w-0">
                                        <p className="text-sm font-medium text-slate-800 truncate">
                                            {s.device_name ?? "Unknown device"}
                                        </p>
                                        <p className="text-xs text-slate-400">
                                            Last used {new Date(s.last_used_at).toLocaleString()}
                                        </p>
                                    </div>
                                    <Button variant="ghost" size="sm" onClick={() => handleRevoke(s.id)}>
                                        Sign out
                                    </Button>
                                </li>
                            ))}
                        </ul>
                    )}
                </Card>
            </div>
        </BuyerShell>
    );
}
