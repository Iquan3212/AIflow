import { useEffect, useMemo, useState } from "react";
import {
    Calendar,
    Clock,
    CheckCircle2,
    XCircle,
    RefreshCw,
    Plus,
    Link2,
    Unlink,
    AlertTriangle,
    User,
} from "lucide-react";

import { useAgency } from "../../context/AgencyContext";
import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import type { BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import Input, { Label } from "../../components/ui/Input";
import { LoadingState, EmptyState } from "../../components/ui/States";
import {
    listAppointments,
    getAvailability,
    bookAppointment,
    rescheduleAppointment,
    cancelAppointment,
    getHours,
    updateHours,
    getRules,
    updateRules,
    getGoogleStatus,
    getGoogleConnectUrl,
    disconnectGoogle,
    type Appointment,
    type Slot,
    type BusinessHoursItem,
    type SchedulingRules,
    type GoogleStatus,
} from "../../services/appointments";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const STATUS_TONE: Record<string, BadgeTone> = {
    scheduled: "info",
    confirmed: "success",
    rescheduled: "warning",
    completed: "success",
    cancelled: "danger",
    no_show: "danger",
};

function todayISO(): string {
    return new Date().toISOString().slice(0, 10);
}

function useTz(): string {
    const { agency } = useAgency();
    return agency?.timezone || "Asia/Kolkata";
}

function fmt(utcIso: string, tz: string): string {
    try {
        return new Intl.DateTimeFormat("en-GB", {
            timeZone: tz,
            weekday: "short",
            day: "2-digit",
            month: "short",
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        }).format(new Date(utcIso));
    } catch {
        return new Date(utcIso).toLocaleString();
    }
}

function GoogleCard({ google, onConnect, onDisconnect }: {
    google: GoogleStatus | null; onConnect: () => void; onDisconnect: () => void;
}) {
    return (
        <Card className="p-5 flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-4">
                <div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center shrink-0">
                    <Calendar size={20} aria-hidden="true" />
                </div>
                <div>
                    <p className="font-semibold text-ink-950">Google Calendar</p>
                    <p className="text-sm text-slate-500">
                        {google?.connected
                            ? "Connected — new site visits sync automatically."
                            : "Sync every site visit to your Google Calendar automatically."}
                    </p>
                </div>
            </div>
            {!google?.available && (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 bg-amber-50 rounded-lg px-3 py-1.5">
                    <AlertTriangle size={13} /> Not configured on server
                </span>
            )}
            {google?.available && google?.connected && (
                <Button variant="secondary" size="sm" onClick={onDisconnect}>
                    <Unlink size={15} /> Disconnect
                </Button>
            )}
            {google?.available && !google?.connected && (
                <Button size="sm" onClick={onConnect}>
                    <Link2 size={15} /> Connect
                </Button>
            )}
        </Card>
    );
}

export default function Appointments() {
    const tz = useTz();

    const [appointments, setAppointments] = useState<Appointment[]>([]);
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);

    const [date, setDate] = useState(todayISO());
    const [slots, setSlots] = useState<Slot[]>([]);
    const [loadingSlots, setLoadingSlots] = useState(false);
    const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
    const [form, setForm] = useState({ name: "", phone: "", email: "", service: "" });
    const [booking, setBooking] = useState(false);

    const [hours, setHours] = useState<BusinessHoursItem[]>([]);
    const [rules, setRules] = useState<SchedulingRules | null>(null);
    const [savingSettings, setSavingSettings] = useState(false);

    const [google, setGoogle] = useState<GoogleStatus | null>(null);

    const [rescheduleFor, setRescheduleFor] = useState<Appointment | null>(null);
    const [rescheduleValue, setRescheduleValue] = useState("");

    function flash(kind: "ok" | "err", msg: string) {
        setToast({ kind, msg });
        setTimeout(() => setToast(null), 3500);
    }

    async function refreshAppointments() {
        setAppointments(await listAppointments());
    }

    useEffect(() => {
        (async () => {
            try {
                await Promise.all([
                    refreshAppointments(),
                    getHours().then(setHours),
                    getRules().then(setRules),
                    getGoogleStatus().then(setGoogle).catch(() => setGoogle(null)),
                ]);
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        })();

        const params = new URLSearchParams(window.location.search);
        const cal = params.get("calendar");
        if (cal === "connected") flash("ok", "Google Calendar connected.");
        else if (cal === "error") flash("err", "Google Calendar connection failed.");
        else if (cal === "invalid_state") flash("err", "Calendar link expired — try again.");
        if (cal) window.history.replaceState({}, "", window.location.pathname);
    }, []);

    const stats = useMemo(() => {
        const now = Date.now();
        const active = appointments.filter((a) => a.status !== "cancelled");
        const upcoming = active.filter((a) => new Date(a.scheduled_at).getTime() >= now);
        const todayCount = active.filter((a) => new Date(a.scheduled_at).toDateString() === new Date().toDateString()).length;
        const cancelled = appointments.filter((a) => a.status === "cancelled").length;
        return { upcoming: upcoming.length, today: todayCount, cancelled, total: appointments.length };
    }, [appointments]);

    async function loadSlots() {
        setLoadingSlots(true);
        setSelectedSlot(null);
        try {
            const data = await getAvailability(date);
            setSlots(data.slots);
            if (data.slots.length === 0) flash("err", "No open slots that day.");
        } catch {
            flash("err", "Couldn't load availability.");
        } finally {
            setLoadingSlots(false);
        }
    }

    async function submitBooking() {
        if (!selectedSlot) return flash("err", "Pick a time slot first.");
        if (!form.name.trim()) return flash("err", "Buyer name is required.");
        if (!form.phone.trim() && !form.email.trim()) return flash("err", "Add a phone or email.");
        setBooking(true);
        try {
            await bookAppointment({
                start_local_iso: selectedSlot.start_local_iso,
                customer_name: form.name.trim(),
                customer_phone: form.phone.trim() || undefined,
                customer_email: form.email.trim() || undefined,
                service: form.service.trim() || undefined,
            });
            flash("ok", "Site visit booked.");
            setForm({ name: "", phone: "", email: "", service: "" });
            setSelectedSlot(null);
            await Promise.all([refreshAppointments(), loadSlots()]);
        } catch (e) {
            const detail = (e as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail;
            flash("err", detail?.message || "That slot is no longer available.");
        } finally {
            setBooking(false);
        }
    }

    async function doReschedule() {
        if (!rescheduleFor || !rescheduleValue) return;
        try {
            await rescheduleAppointment(rescheduleFor.id, rescheduleValue);
            flash("ok", "Site visit rescheduled.");
            setRescheduleFor(null);
            setRescheduleValue("");
            await refreshAppointments();
        } catch (e) {
            const detail = (e as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail;
            flash("err", detail?.message || "Couldn't reschedule to that time.");
        }
    }

    async function doCancel(a: Appointment) {
        if (!window.confirm(`Cancel the site visit for ${a.customer_name || "this buyer"}?`)) return;
        try {
            await cancelAppointment(a.id);
            flash("ok", "Site visit cancelled.");
            await refreshAppointments();
        } catch {
            flash("err", "Couldn't cancel.");
        }
    }

    async function saveSettings() {
        setSavingSettings(true);
        try {
            await updateHours(hours);
            if (rules) await updateRules(rules);
            flash("ok", "Availability settings saved.");
        } catch {
            flash("err", "Couldn't save settings.");
        } finally {
            setSavingSettings(false);
        }
    }

    async function connectGoogle() {
        try {
            window.location.href = await getGoogleConnectUrl();
        } catch (e) {
            const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            flash("err", detail || "Google is not configured on the server.");
        }
    }

    async function disconnect() {
        try {
            await disconnectGoogle();
            setGoogle((g) => (g ? { ...g, connected: false } : g));
            flash("ok", "Google Calendar disconnected.");
        } catch {
            flash("err", "Couldn't disconnect.");
        }
    }

    if (loading) return <AppShell><LoadingState label="Loading site visits…" /></AppShell>;

    return (
        <AppShell>
            <PageHeader
                eyebrow="Operations"
                title="Site Visits"
                description="Your AI receptionist books, reschedules, and reminds buyers — manage it all here."
            />

            {toast && (
                <div
                    role="status"
                    className={`fixed top-20 right-6 z-40 rounded-xl px-4 py-3 text-sm font-medium shadow-lifted ${
                        toast.kind === "ok" ? "bg-brand-600 text-white" : "bg-red-600 text-white"
                    }`}
                >
                    {toast.msg}
                </div>
            )}

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
                <Card className="p-5"><p className="text-xs text-slate-500">Upcoming</p><p className="font-display text-3xl font-medium text-ink-950 mt-1 flex items-center gap-2"><Clock size={18} className="text-brand-500" />{stats.upcoming}</p></Card>
                <Card className="p-5"><p className="text-xs text-slate-500">Today</p><p className="font-display text-3xl font-medium text-ink-950 mt-1 flex items-center gap-2"><Calendar size={18} className="text-flare-500" />{stats.today}</p></Card>
                <Card className="p-5"><p className="text-xs text-slate-500">Total booked</p><p className="font-display text-3xl font-medium text-ink-950 mt-1 flex items-center gap-2"><CheckCircle2 size={18} className="text-slate-400" />{stats.total}</p></Card>
                <Card className="p-5"><p className="text-xs text-slate-500">Cancelled</p><p className="font-display text-3xl font-medium text-ink-950 mt-1 flex items-center gap-2"><XCircle size={18} className="text-red-400" />{stats.cancelled}</p></Card>
            </div>

            <div className="mb-5">
                <GoogleCard google={google} onConnect={connectGoogle} onDisconnect={disconnect} />
            </div>

            <div className="grid lg:grid-cols-2 gap-5 mb-5">
                <Card className="p-6">
                    <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-4"><Plus size={16} /> Book a site visit</h2>

                    <div className="flex items-end gap-3 mb-4">
                        <div className="flex-1">
                            <Label htmlFor="visit-date">Date</Label>
                            <Input id="visit-date" type="date" value={date} min={todayISO()} onChange={(e) => setDate(e.target.value)} />
                        </div>
                        <Button variant="secondary" onClick={loadSlots} disabled={loadingSlots}>
                            {loadingSlots ? "Loading…" : "Check availability"}
                        </Button>
                    </div>

                    {slots.length > 0 && (
                        <div className="grid grid-cols-4 gap-2 mb-4">
                            {slots.map((s) => {
                                const time = s.start_local_iso.slice(11);
                                const active = selectedSlot?.start_local_iso === s.start_local_iso;
                                return (
                                    <button
                                        key={s.start_local_iso}
                                        onClick={() => setSelectedSlot(s)}
                                        title={s.label}
                                        className={`text-sm font-medium rounded-lg py-2 transition-colors ${
                                            active ? "bg-brand-600 text-white" : "bg-stone-100 text-ink-950 hover:bg-stone-200"
                                        }`}
                                    >
                                        {time}
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {selectedSlot && (
                        <div className="space-y-3 rounded-xl bg-stone-100 p-4">
                            <p className="text-sm text-ink-950">Selected: <strong>{selectedSlot.label}</strong></p>
                            <Input placeholder="Buyer name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                            <div className="grid grid-cols-2 gap-3">
                                <Input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                                <Input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                            </div>
                            <Input placeholder="Property / service (optional)" value={form.service} onChange={(e) => setForm({ ...form, service: e.target.value })} />
                            <Button onClick={submitBooking} loading={booking} className="w-full">Confirm site visit</Button>
                        </div>
                    )}
                </Card>

                <Card className="p-6">
                    <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-4"><Clock size={16} /> Availability settings</h2>

                    <div className="space-y-2 mb-5">
                        {hours.slice().sort((a, b) => a.weekday - b.weekday).map((h) => (
                            <div key={h.weekday} className="flex items-center gap-3">
                                <span className="w-9 text-xs font-medium text-slate-500">{WEEKDAYS[h.weekday]}</span>
                                <label className="relative inline-flex items-center cursor-pointer shrink-0">
                                    <input
                                        type="checkbox"
                                        checked={h.is_open}
                                        onChange={(e) => setHours((prev) => prev.map((x) => (x.weekday === h.weekday ? { ...x, is_open: e.target.checked } : x)))}
                                        className="sr-only peer"
                                    />
                                    <div className="w-9 h-5 bg-slate-200 rounded-full peer peer-checked:bg-brand-600 transition-colors" />
                                    <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4" />
                                </label>
                                <input
                                    type="time"
                                    disabled={!h.is_open}
                                    value={h.open_time || "10:00"}
                                    onChange={(e) => setHours((prev) => prev.map((x) => (x.weekday === h.weekday ? { ...x, open_time: e.target.value } : x)))}
                                    className="text-xs rounded-lg border border-slate-200 px-2 py-1 disabled:opacity-40 outline-none focus:border-brand-500"
                                />
                                <span className="text-slate-300">–</span>
                                <input
                                    type="time"
                                    disabled={!h.is_open}
                                    value={h.close_time || "18:00"}
                                    onChange={(e) => setHours((prev) => prev.map((x) => (x.weekday === h.weekday ? { ...x, close_time: e.target.value } : x)))}
                                    className="text-xs rounded-lg border border-slate-200 px-2 py-1 disabled:opacity-40 outline-none focus:border-brand-500"
                                />
                            </div>
                        ))}
                    </div>

                    {rules && (
                        <div className="grid grid-cols-2 gap-3 mb-5">
                            {([
                                ["Slot (min)", "slot_duration_minutes"],
                                ["Buffer (min)", "buffer_minutes"],
                                ["Min notice (min)", "min_notice_minutes"],
                                ["Max advance (days)", "max_advance_days"],
                            ] as const).map(([label, key]) => (
                                <div key={key}>
                                    <Label htmlFor={key}>{label}</Label>
                                    <Input
                                        id={key}
                                        type="number"
                                        min={0}
                                        value={rules[key]}
                                        onChange={(e) => setRules({ ...rules, [key]: parseInt(e.target.value || "0", 10) })}
                                    />
                                </div>
                            ))}
                        </div>
                    )}

                    <Button onClick={saveSettings} loading={savingSettings} variant="secondary" className="w-full">Save settings</Button>
                </Card>
            </div>

            <Card className="p-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2"><Calendar size={16} /> All site visits</h2>
                    <Button variant="ghost" size="sm" onClick={() => refreshAppointments()}><RefreshCw size={14} /> Refresh</Button>
                </div>

                {appointments.length === 0 ? (
                    <EmptyState icon={<Calendar size={28} />} title="No site visits yet" description="Bookings from your AI receptionist will appear here." />
                ) : (
                    <ul className="divide-y divide-slate-100">
                        {appointments.map((a) => (
                            <li key={a.id} className="py-3.5 flex items-center gap-4 flex-wrap">
                                <div className="w-9 h-9 rounded-full bg-stone-100 text-slate-400 flex items-center justify-center shrink-0">
                                    <User size={16} />
                                </div>
                                <div className="min-w-0 flex-1">
                                    <p className="text-sm font-medium text-ink-950 truncate">{a.customer_name || "—"}</p>
                                    <p className="text-xs text-slate-500 truncate">
                                        {a.service || "No property specified"} · {fmt(a.scheduled_at, tz)}
                                    </p>
                                </div>
                                <Badge tone="neutral" className="hidden sm:inline-flex">{a.source}</Badge>
                                <Badge tone={STATUS_TONE[a.status] ?? "neutral"}>{a.status.replace("_", " ")}</Badge>
                                {a.status !== "cancelled" && (
                                    <div className="flex items-center gap-1">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => { setRescheduleFor(a); setRescheduleValue(a.scheduled_at.slice(0, 16)); }}
                                        >
                                            Reschedule
                                        </Button>
                                        <Button variant="ghost" size="sm" className="!text-red-600 hover:!bg-red-50" onClick={() => doCancel(a)}>
                                            Cancel
                                        </Button>
                                    </div>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </Card>

            {rescheduleFor && (
                <Modal title="Reschedule site visit" onClose={() => setRescheduleFor(null)}>
                    <p className="text-sm text-slate-500 mb-4">
                        {rescheduleFor.customer_name} — currently {fmt(rescheduleFor.scheduled_at, tz)}
                    </p>
                    <Label htmlFor="reschedule-time">{`New time (${tz})`}</Label>
                    <Input id="reschedule-time" type="datetime-local" value={rescheduleValue} onChange={(e) => setRescheduleValue(e.target.value)} />
                    <div className="flex justify-end gap-2 mt-5">
                        <Button variant="secondary" onClick={() => setRescheduleFor(null)}>Cancel</Button>
                        <Button onClick={doReschedule}>Save new time</Button>
                    </div>
                </Modal>
            )}
        </AppShell>
    );
}
