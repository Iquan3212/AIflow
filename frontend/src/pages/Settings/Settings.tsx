import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Trash2 } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import { ErrorState, LoadingState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getCurrentBusiness, updateCurrentBusiness } from "../../services/business";
import { getChatbotConfig, updateChatbotConfig } from "../../services/chatbot";
import { listSessions, revokeSession, type Session } from "../../services/sessions";
import { getGoogleStatus, type GoogleStatus } from "../../services/appointments";
import type { Business } from "../../services/business";
import type { ChatbotConfig } from "../../types/chatbot";

const TABS = ["Business", "AI", "Integrations", "Notifications", "Security"] as const;
type Tab = (typeof TABS)[number];

function SavedBadge({ show }: { show: boolean }) {
    if (!show) return null;
    return (
        <span className="inline-flex items-center gap-1 text-emerald-600 text-sm">
            <Check size={14} /> Saved
        </span>
    );
}

function BusinessTab() {
    const [business, setBusiness] = useState<Business | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [form, setForm] = useState({ name: "", industry: "", timezone: "" });
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    async function load() {
        setError(null);
        try {
            const data = await getCurrentBusiness();
            setBusiness(data);
            setForm({ name: data.name, industry: data.industry ?? "", timezone: data.timezone });
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    async function handleSave() {
        setSaving(true);
        setSaved(false);
        setError(null);
        try {
            const updated = await updateCurrentBusiness(form);
            setBusiness(updated);
            setSaved(true);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    if (!business && !error) return <LoadingState label="Loading business profile…" />;
    if (error && !business) return <ErrorState message={error} onRetry={load} />;

    return (
        <Card className="p-5 max-w-lg space-y-4">
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="biz-name">Business name</label>
                <input
                    id="biz-name"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    className="w-full mt-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                />
            </div>
            <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="biz-industry">Industry</label>
                <input
                    id="biz-industry"
                    value={form.industry}
                    onChange={(e) => setForm((f) => ({ ...f, industry: e.target.value }))}
                    className="w-full mt-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                />
            </div>
            <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="biz-tz">Timezone</label>
                <input
                    id="biz-tz"
                    value={form.timezone}
                    onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
                    placeholder="e.g. Asia/Kolkata"
                    className="w-full mt-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                />
            </div>
            <div className="grid grid-cols-2 gap-4 pt-2 text-sm text-slate-500">
                <div>
                    <p className="text-xs text-slate-400">Plan</p>
                    <p className="font-medium text-slate-700">{business?.plan?.toUpperCase()}</p>
                </div>
                <div>
                    <p className="text-xs text-slate-400">Contact email</p>
                    <p className="font-medium text-slate-700">{business?.contact_email}</p>
                </div>
            </div>
            <div className="flex items-center gap-3 pt-2">
                <Button onClick={handleSave} loading={saving}>Save changes</Button>
                <SavedBadge show={saved} />
            </div>
        </Card>
    );
}

function AiTab() {
    const [config, setConfig] = useState<ChatbotConfig | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [form, setForm] = useState({ business_description: "", persona_tone: "", welcome_message: "" });
    const [services, setServices] = useState<string[]>([]);
    const [newService, setNewService] = useState("");
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    async function load() {
        setError(null);
        try {
            const data = await getChatbotConfig();
            setConfig(data);
            setForm({
                business_description: data.business_description,
                persona_tone: data.persona_tone,
                welcome_message: data.welcome_message,
            });
            setServices(data.services);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    async function handleSave() {
        setSaving(true);
        setSaved(false);
        setError(null);
        try {
            const updated = await updateChatbotConfig({ ...form, services });
            setConfig(updated);
            setSaved(true);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    if (!config && !error) return <LoadingState label="Loading AI configuration…" />;
    if (error && !config) return <ErrorState message={error} onRetry={load} />;

    return (
        <Card className="p-5 max-w-xl space-y-4">
            {error && <p className="text-sm text-red-600">{error}</p>}
            <p className="text-sm text-slate-500">
                This grounds every AI Workforce reply - what it knows about your business, and its tone.
            </p>
            <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="ai-desc">Business description</label>
                <textarea
                    id="ai-desc"
                    rows={3}
                    value={form.business_description}
                    onChange={(e) => setForm((f) => ({ ...f, business_description: e.target.value }))}
                    className="w-full mt-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                />
            </div>
            <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="ai-tone">Tone</label>
                <input
                    id="ai-tone"
                    value={form.persona_tone}
                    onChange={(e) => setForm((f) => ({ ...f, persona_tone: e.target.value }))}
                    placeholder="e.g. friendly and professional"
                    className="w-full mt-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                />
            </div>
            <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="ai-welcome">Welcome message</label>
                <input
                    id="ai-welcome"
                    value={form.welcome_message}
                    onChange={(e) => setForm((f) => ({ ...f, welcome_message: e.target.value }))}
                    className="w-full mt-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                />
            </div>
            <div>
                <label className="text-sm font-medium text-slate-700">Services</label>
                <div className="flex flex-wrap gap-2 mt-2">
                    {services.map((s) => (
                        <Badge key={s} tone="info">
                            {s}
                            <button
                                type="button"
                                onClick={() => setServices((list) => list.filter((x) => x !== s))}
                                aria-label={`Remove ${s}`}
                                className="ml-1.5"
                            >
                                ×
                            </button>
                        </Badge>
                    ))}
                </div>
                <div className="flex gap-2 mt-2">
                    <input
                        value={newService}
                        onChange={(e) => setNewService(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && newService.trim()) {
                                e.preventDefault();
                                setServices((list) => [...list, newService.trim()]);
                                setNewService("");
                            }
                        }}
                        placeholder="Add a service and press Enter"
                        className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                    />
                </div>
            </div>
            <div className="flex items-center gap-3 pt-2">
                <Button onClick={handleSave} loading={saving}>Save changes</Button>
                <SavedBadge show={saved} />
            </div>
        </Card>
    );
}

function IntegrationsTab() {
    const navigate = useNavigate();
    const [status, setStatus] = useState<GoogleStatus | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setStatus(await getGoogleStatus());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    if (!status && !error) return <LoadingState label="Loading integrations…" />;
    if (error) return <ErrorState message={error} onRetry={load} />;

    return (
        <Card className="p-5 max-w-lg">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm font-medium text-slate-800">Google Calendar</p>
                    <p className="text-xs text-slate-500 mt-0.5">Syncs every booking, reschedule, and cancellation.</p>
                </div>
                <Badge tone={status?.connected ? "success" : "neutral"}>
                    {status?.connected ? "Connected" : "Not connected"}
                </Badge>
            </div>
            <Button variant="secondary" size="sm" className="mt-4" onClick={() => navigate("/appointments")}>
                Manage in Appointments
            </Button>
        </Card>
    );
}

function NotificationsTab() {
    return (
        <Card className="p-5 max-w-lg">
            <EmptyState
                title="Not configurable yet"
                description="Appointment confirmations and reminders are sent automatically by email (or SMS/WhatsApp, once configured on the server) - there's no per-channel toggle here yet."
            />
        </Card>
    );
}

function SecurityTab() {
    const [sessions, setSessions] = useState<Session[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setSessions(await listSessions());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    async function handleRevoke(id: string) {
        const previous = sessions;
        setSessions((current) => current?.filter((s) => s.id !== id) ?? current);
        try {
            await revokeSession(id);
        } catch (err) {
            setSessions(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    return (
        <Card className="p-5 max-w-lg">
            <h3 className="text-sm font-semibold text-slate-700 mb-1">Active sessions</h3>
            <p className="text-xs text-slate-500 mb-4">Everywhere you're currently signed in to AIFlow.</p>

            {sessions === null && !error && <LoadingState label="Loading sessions…" />}
            {error && <ErrorState message={error} onRetry={load} />}
            {sessions && sessions.length === 0 && <EmptyState title="No active sessions" />}
            {sessions && sessions.length > 0 && (
                <ul className="divide-y divide-slate-100">
                    {sessions.map((s) => (
                        <li key={s.id} className="py-3 flex items-center justify-between gap-4">
                            <div className="min-w-0">
                                <p className="text-sm text-slate-800 truncate">{s.device_name ?? "Unknown device"}</p>
                                <p className="text-xs text-slate-400">
                                    {s.ip_address ?? "Unknown IP"} · last active {new Date(s.last_used_at).toLocaleString()}
                                </p>
                            </div>
                            <button
                                onClick={() => handleRevoke(s.id)}
                                aria-label="Revoke session"
                                className="text-slate-400 hover:text-red-600 shrink-0"
                            >
                                <Trash2 size={16} />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </Card>
    );
}

export default function Settings() {
    const [tab, setTab] = useState<Tab>("Business");

    return (
        <AppShell>
            <PageHeader title="Settings" description="Configure your business profile, AI behavior, and account security." />

            <div className="flex gap-1 border-b border-slate-200 mb-6 overflow-x-auto" role="tablist">
                {TABS.map((t) => (
                    <button
                        key={t}
                        role="tab"
                        aria-selected={tab === t}
                        onClick={() => setTab(t)}
                        className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px ${
                            tab === t ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-500 hover:text-slate-700"
                        }`}
                    >
                        {t}
                    </button>
                ))}
            </div>

            {tab === "Business" && <BusinessTab />}
            {tab === "AI" && <AiTab />}
            {tab === "Integrations" && <IntegrationsTab />}
            {tab === "Notifications" && <NotificationsTab />}
            {tab === "Security" && <SecurityTab />}
        </AppShell>
    );
}
