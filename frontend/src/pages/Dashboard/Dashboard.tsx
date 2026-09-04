import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarClock, MessageCircle, Sparkles, Users } from "lucide-react";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
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
import { useBusiness } from "../../context/BusinessContext";

function greeting(): string {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
}

export default function Dashboard() {
    const navigate = useNavigate();
    const { business } = useBusiness();

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
            <PageHeader
                title={`${greeting()}, ${business?.name ?? "there"}`}
                description="Here's what's happening across your AI Workforce."
            />

            {!stats && !error && <LoadingState label="Loading dashboard…" />}
            {error && <ErrorState message={error} onRetry={load} />}

            {stats && !error && (
                <div className="space-y-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                        <StatCard label="Today's chats" value={stats.today_chats} icon={<MessageCircle size={18} />} />
                        <StatCard label="New leads today" value={stats.new_leads_today} icon={<Users size={18} />} />
                        <StatCard
                            label="Upcoming appointments"
                            value={stats.upcoming_appointments}
                            icon={<CalendarClock size={18} />}
                        />
                        <StatCard label="Total leads" value={stats.total_leads} icon={<Sparkles size={18} />} />
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <Card className="p-5 lg:col-span-2">
                            <h2 className="text-sm font-semibold text-slate-700 mb-4">Conversations, last 14 days</h2>
                            {analytics && analytics.conversations_per_day.some((p) => p.count > 0) ? (
                                <div style={{ width: "100%", height: 220 }}>
                                    <ResponsiveContainer>
                                        <LineChart data={analytics.conversations_per_day}>
                                            <XAxis
                                                dataKey="date"
                                                tickFormatter={(d) => new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                                                fontSize={12}
                                            />
                                            <YAxis allowDecimals={false} fontSize={12} width={28} />
                                            <Tooltip labelFormatter={(d) => new Date(d as string).toLocaleDateString()} />
                                            <Line dataKey="count" stroke="#4f46e5" strokeWidth={2} dot={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <EmptyState title="No conversations yet" description="Activity will appear here once customers start chatting." />
                            )}
                        </Card>

                        <Card className="p-5">
                            <h2 className="text-sm font-semibold text-slate-700 mb-4">AI status</h2>
                            <dl className="space-y-3 text-sm">
                                <div className="flex justify-between">
                                    <dt className="text-slate-500">Status</dt>
                                    <dd><Badge tone="success">Online</Badge></dd>
                                </div>
                                <div className="flex justify-between">
                                    <dt className="text-slate-500">Model</dt>
                                    <dd className="text-slate-700 font-medium">{stats.model}</dd>
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

                    <Card className="p-5">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-sm font-semibold text-slate-700">Recent leads</h2>
                            <button onClick={() => navigate("/leads")} className="text-sm text-indigo-600 hover:underline">
                                View all
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
                                                {lead.service_interested ?? "No service specified"}
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
