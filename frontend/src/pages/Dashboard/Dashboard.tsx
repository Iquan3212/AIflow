import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarClock, MessageCircle, Sparkles, Users, ArrowUpRight } from "lucide-react";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

import AppShell from "../../components/layout/AppShell";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import StatCard from "../../components/ui/StatCard";
import Badge from "../../components/ui/Badge";
import { ErrorState, LoadingState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getDashboardStats, type DashboardStats } from "../../services/dashboard";
import { getAnalyticsOverview, type AnalyticsOverview } from "../../services/analytics";
import { listLeads } from "../../services/leads";
import type { Lead } from "../../types/lead";
import { useAgency } from "../../context/AgencyContext";

function greeting(): string {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
}

export default function Dashboard() {
    const navigate = useNavigate();
    const { agency } = useAgency();

    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
    const [recentLeads, setRecentLeads] = useState<Lead[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            const [statsData, analyticsData, leadsData] = await Promise.all([
                getDashboardStats(),
                getAnalyticsOverview(),
                listLeads(),
            ]);
            setStats(statsData);
            setAnalytics(analyticsData);
            setRecentLeads(leadsData.slice(0, 5));
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        load();
    }, []);

    return (
        <AppShell>
            <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Agency operating system</p>
                    <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">
                        {greeting()}, {agency?.name ?? "there"}
                    </h1>
                    <p className="text-sm text-slate-500 mt-1.5 max-w-xl">Here's what's happening across your AI Workforce.</p>
                </div>
            </div>

            {!stats && !error && <LoadingState label="Loading dashboard…" />}
            {error && <ErrorState message={error} onRetry={load} />}

            {stats && !error && (
                <div className="space-y-5">
                    <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1.6fr] gap-4">
                        <div className="rounded-3xl bg-ink-950 text-white p-7 flex flex-col justify-between min-h-[11rem] relative overflow-hidden">
                            <div className="absolute inset-0 bg-dot-grid opacity-30" aria-hidden="true" />
                            <div className="relative w-10 h-10 rounded-xl bg-white/10 text-flare-400 flex items-center justify-center">
                                <MessageCircle size={18} aria-hidden="true" />
                            </div>
                            <div className="relative">
                                <p className="text-sm text-slate-400">Today&apos;s chats</p>
                                <p className="font-display text-6xl font-medium tracking-tight mt-1.5">{stats.today_chats}</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <StatCard label="New leads today" value={stats.new_leads_today} icon={<Users size={18} />} />
                            <StatCard
                                label="Upcoming site visits"
                                value={stats.upcoming_appointments}
                                icon={<CalendarClock size={18} />}
                            />
                            <StatCard label="Total leads" value={stats.total_leads} icon={<Sparkles size={18} />} />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <Card className="p-6 lg:col-span-2">
                            <h2 className="text-sm font-semibold text-slate-700 mb-4">Conversations, last 14 days</h2>
                            {analytics && analytics.conversations_per_day.some((p) => p.count > 0) ? (
                                <div style={{ width: "100%", height: 220 }}>
                                    <ResponsiveContainer>
                                        <LineChart data={analytics.conversations_per_day}>
                                            <XAxis
                                                dataKey="date"
                                                tickFormatter={(d) => new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                                                fontSize={12}
                                                stroke="var(--color-slate-400)"
                                            />
                                            <YAxis allowDecimals={false} fontSize={12} width={28} stroke="var(--color-slate-400)" />
                                            <Tooltip labelFormatter={(d) => new Date(d as string).toLocaleDateString()} />
                                            <Line dataKey="count" stroke="var(--color-brand-600)" strokeWidth={2.5} dot={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <EmptyState title="No conversations yet" description="Activity will appear here once buyers start chatting." />
                            )}
                        </Card>

                        <Card className="p-6">
                            <h2 className="text-sm font-semibold text-slate-700 mb-4">AI status</h2>
                            <dl className="space-y-3 text-sm">
                                <div className="flex justify-between">
                                    <dt className="text-slate-500">Status</dt>
                                    <dd><Badge tone="success">Online</Badge></dd>
                                </div>
                                <div className="flex justify-between">
                                    <dt className="text-slate-500">Model</dt>
                                    <dd className="text-slate-700 font-medium font-mono-data text-xs">{stats.model}</dd>
                                </div>
                                <div className="flex justify-between">
                                    <dt className="text-slate-500">Avg. response time</dt>
                                    <dd className="text-slate-700 font-medium">
                                        {stats.avg_response_time_seconds != null
                                            ? `${stats.avg_response_time_seconds}s`
                                            : "Not enough data yet"}
                                    </dd>
                                </div>
                            </dl>
                            <div className="mt-5 flex flex-col gap-2">
                                <Button size="sm" onClick={() => navigate("/manager")}>Open Manager AI</Button>
                                <Button size="sm" variant="secondary" onClick={() => navigate("/workforce")}>View AI Workforce</Button>
                            </div>
                        </Card>
                    </div>

                    <Card className="p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-sm font-semibold text-slate-700">Recent leads</h2>
                            <button
                                onClick={() => navigate("/leads")}
                                className="inline-flex items-center gap-1 text-sm text-brand-600 font-medium hover:text-brand-700"
                            >
                                View all <ArrowUpRight size={14} />
                            </button>
                        </div>
                        {recentLeads && recentLeads.length === 0 && (
                            <EmptyState title="No leads yet" description="New leads captured by your AI Workforce will appear here." />
                        )}
                        {recentLeads && recentLeads.length > 0 && (
                            <ul className="divide-y divide-slate-100">
                                {recentLeads.map((lead) => (
                                    <li key={lead.id} className="py-3 flex items-center justify-between gap-4">
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-slate-800 truncate">{lead.name ?? "Unnamed lead"}</p>
                                            <p className="text-xs text-slate-500 truncate">
                                                {lead.service_interested ?? "No preference specified"}
                                                {lead.budget ? ` · ${lead.budget}` : ""}
                                            </p>
                                        </div>
                                        <Badge tone="info">{lead.status}</Badge>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </Card>
                </div>
            )}
        </AppShell>
    );
}
