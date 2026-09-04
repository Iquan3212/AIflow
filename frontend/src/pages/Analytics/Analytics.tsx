import { useEffect, useState } from "react";
import { BarChart3, CalendarClock, MessageCircle, Users } from "lucide-react";
import { BarChart, Bar, LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import StatCard from "../../components/ui/StatCard";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getAnalyticsOverview, type AnalyticsOverview } from "../../services/analytics";

function formatDay(d: string) {
    return new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function StatusBreakdown({ title, data }: { title: string; data: Record<string, number> }) {
    const entries = Object.entries(data);
    const total = entries.reduce((sum, [, count]) => sum + count, 0);

    return (
        <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">{title}</h2>
            {entries.length === 0 || total === 0 ? (
                <EmptyState title="No data yet" />
            ) : (
                <div className="space-y-3">
                    {entries.map(([status, count]) => (
                        <div key={status}>
                            <div className="flex justify-between text-xs text-slate-500 mb-1">
                                <span className="capitalize">{status}</span>
                                <span>{count}</span>
                            </div>
                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-indigo-500 rounded-full"
                                    style={{ width: `${total ? (count / total) * 100 : 0}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </Card>
    );
}

function TrendCard({ title, data, color }: { title: string; data: { date: string; count: number }[]; color: string }) {
    const hasData = data.some((p) => p.count > 0);
    return (
        <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">{title}</h2>
            {hasData ? (
                <div style={{ width: "100%", height: 200 }}>
                    <ResponsiveContainer>
                        <BarChart data={data}>
                            <CartesianGrid vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="date" tickFormatter={formatDay} fontSize={12} interval={2} />
                            <YAxis allowDecimals={false} fontSize={12} width={28} />
                            <Tooltip labelFormatter={(d) => new Date(d as string).toLocaleDateString()} />
                            <Bar dataKey="count" fill={color} radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            ) : (
                <EmptyState title="No data in the last 14 days" />
            )}
        </Card>
    );
}

export default function Analytics() {
    const [data, setData] = useState<AnalyticsOverview | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setData(await getAnalyticsOverview());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    const converted = data?.leads_by_status?.converted ?? 0;
    const conversionRate = data && data.total_leads > 0 ? Math.round((converted / data.total_leads) * 100) : null;

    return (
        <AppShell>
            <PageHeader title="Analytics" description="Real counts and trends from your business data, over the last 14 days." />

            {!data && !error && <LoadingState label="Loading analytics…" />}
            {error && <ErrorState message={error} onRetry={load} />}

            {data && !error && (
                <div className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                        <StatCard label="Total leads" value={data.total_leads} icon={<Users size={18} />} />
                        <StatCard label="Total appointments" value={data.total_appointments} icon={<CalendarClock size={18} />} />
                        <StatCard label="Total conversations" value={data.total_conversations} icon={<MessageCircle size={18} />} />
                        <StatCard
                            label="Lead conversion rate"
                            value={conversionRate != null ? `${conversionRate}%` : "—"}
                            icon={<BarChart3 size={18} />}
                            hint={conversionRate != null ? "Leads marked converted" : "No leads yet"}
                        />
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <TrendCard title="Leads per day" data={data.leads_per_day} color="#4f46e5" />
                        <TrendCard title="Appointments per day" data={data.appointments_per_day} color="#0ea5e9" />
                    </div>

                    <Card className="p-5">
                        <h2 className="text-sm font-semibold text-slate-700 mb-4">Conversations per day</h2>
                        {data.conversations_per_day.some((p) => p.count > 0) ? (
                            <div style={{ width: "100%", height: 220 }}>
                                <ResponsiveContainer>
                                    <LineChart data={data.conversations_per_day}>
                                        <CartesianGrid vertical={false} stroke="#f1f5f9" />
                                        <XAxis dataKey="date" tickFormatter={formatDay} fontSize={12} />
                                        <YAxis allowDecimals={false} fontSize={12} width={28} />
                                        <Tooltip labelFormatter={(d) => new Date(d as string).toLocaleDateString()} />
                                        <Line dataKey="count" stroke="#16a34a" strokeWidth={2} dot={false} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        ) : (
                            <EmptyState title="No conversations in the last 14 days" />
                        )}
                    </Card>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <StatusBreakdown title="Leads by status" data={data.leads_by_status} />
                        <StatusBreakdown title="Appointments by status" data={data.appointments_by_status} />
                    </div>
                </div>
            )}
        </AppShell>
    );
}
