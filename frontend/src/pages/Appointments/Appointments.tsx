import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
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
} from "lucide-react";

import { useBusiness } from "../../context/BusinessContext";
import AppShell from "../../components/layout/AppShell";
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

import "./Appointments.css";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function todayISO(): string {
    return new Date().toISOString().slice(0, 10);
}

function useTz(): string {
    const { business } = useBusiness();
    return business?.timezone || "Asia/Kolkata";
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

export default function Appointments() {
    const tz = useTz();

    const [appointments, setAppointments] = useState<Appointment[]>([]);
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);

    // booking panel
    const [date, setDate] = useState(todayISO());
    const [slots, setSlots] = useState<Slot[]>([]);
    const [loadingSlots, setLoadingSlots] = useState(false);
    const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
    const [form, setForm] = useState({ name: "", phone: "", email: "", service: "" });
    const [booking, setBooking] = useState(false);

    // settings
    const [hours, setHours] = useState<BusinessHoursItem[]>([]);
    const [rules, setRules] = useState<SchedulingRules | null>(null);
    const [savingSettings, setSavingSettings] = useState(false);

    // google
    const [google, setGoogle] = useState<GoogleStatus | null>(null);

    // reschedule modal
    const [rescheduleFor, setRescheduleFor] = useState<Appointment | null>(null);
    const [rescheduleValue, setRescheduleValue] = useState("");

    function flash(kind: "ok" | "err", msg: string) {
        setToast({ kind, msg });
        setTimeout(() => setToast(null), 3500);
    }

    async function refreshAppointments() {
        const data = await listAppointments();
        setAppointments(data);
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

        // Feedback after returning from the Google OAuth redirect.
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
        const todayCount = active.filter((a) => {
            const d = new Date(a.scheduled_at);
            const t = new Date();
            return d.toDateString() === t.toDateString();
        }).length;
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
        if (!form.name.trim()) return flash("err", "Customer name is required.");
        if (!form.phone.trim() && !form.email.trim())
            return flash("err", "Add a phone or email.");
        setBooking(true);
        try {
            await bookAppointment({
                start_local_iso: selectedSlot.start_local_iso,
                customer_name: form.name.trim(),
                customer_phone: form.phone.trim() || undefined,
                customer_email: form.email.trim() || undefined,
                service: form.service.trim() || undefined,
            });
            flash("ok", "Appointment booked.");
            setForm({ name: "", phone: "", email: "", service: "" });
            setSelectedSlot(null);
            await Promise.all([refreshAppointments(), loadSlots()]);
        } catch (e: any) {
            const detail = e?.response?.data?.detail;
            flash("err", detail?.message || "That slot is no longer available.");
        } finally {
            setBooking(false);
        }
    }

    async function doReschedule() {
        if (!rescheduleFor || !rescheduleValue) return;
        try {
            await rescheduleAppointment(rescheduleFor.id, rescheduleValue);
            flash("ok", "Appointment rescheduled.");
            setRescheduleFor(null);
            setRescheduleValue("");
            await refreshAppointments();
        } catch (e: any) {
            const detail = e?.response?.data?.detail;
            flash("err", detail?.message || "Couldn't reschedule to that time.");
        }
    }

    async function doCancel(a: Appointment) {
        if (!window.confirm(`Cancel the appointment for ${a.customer_name || "this customer"}?`)) return;
        try {
            await cancelAppointment(a.id);
            flash("ok", "Appointment cancelled.");
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
            const url = await getGoogleConnectUrl();
            window.location.href = url;
        } catch (e: any) {
            flash("err", e?.response?.data?.detail || "Google is not configured on the server.");
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

    if (loading) return <AppShell><div className="appt-loading">Loading appointments…</div></AppShell>;

    return (
        <AppShell>
        <div className="appt-page">
            <div className="page-title">
                <h1>Appointments</h1>
                <p>Your AI receptionist books, reschedules, and reminds — manage it all here.</p>
            </div>

            {toast && <div className={`appt-toast ${toast.kind}`}>{toast.msg}</div>}

            {/* stats */}
            <div className="appt-stats">
                <StatCard icon={<Clock size={18} />} label="Upcoming" value={stats.upcoming} tone="blue" />
                <StatCard icon={<Calendar size={18} />} label="Today" value={stats.today} tone="green" />
                <StatCard icon={<CheckCircle2 size={18} />} label="Total booked" value={stats.total} tone="slate" />
                <StatCard icon={<XCircle size={18} />} label="Cancelled" value={stats.cancelled} tone="red" />
            </div>

            {/* google calendar */}
            <GoogleCard google={google} onConnect={connectGoogle} onDisconnect={disconnect} />

            <div className="appt-grid">
                {/* booking */}
                <section className="appt-card">
                    <h2 className="appt-card-title"><Plus size={18} /> Book an appointment</h2>

                    <div className="appt-row">
                        <label className="appt-label">
                            Date
                            <input
                                type="date"
                                value={date}
                                min={todayISO()}
                                onChange={(e) => setDate(e.target.value)}
                                className="appt-input"
                            />
                        </label>
                        <button className="appt-btn ghost" onClick={loadSlots} disabled={loadingSlots}>
                            {loadingSlots ? "Loading…" : "Check availability"}
                        </button>
                    </div>

                    {slots.length > 0 && (
                        <div className="slot-grid">
                            {slots.map((s) => {
                                const time = s.start_local_iso.slice(11);
                                const active = selectedSlot?.start_local_iso === s.start_local_iso;
                                return (
                                    <button
                                        key={s.start_local_iso}
                                        className={`slot-chip ${active ? "active" : ""}`}
                                        onClick={() => setSelectedSlot(s)}
                                        title={s.label}
                                    >
                                        {time}
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {selectedSlot && (
                        <div className="appt-booking-form">
                            <div className="selected-banner">
                                Selected: <strong>{selectedSlot.label}</strong>
                            </div>
                            <input
                                className="appt-input"
                                placeholder="Customer name *"
                                value={form.name}
                                onChange={(e) => setForm({ ...form, name: e.target.value })}
                            />
                            <div className="appt-row">
                                <input
                                    className="appt-input"
                                    placeholder="Phone"
                                    value={form.phone}
                                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                                />
                                <input
                                    className="appt-input"
                                    placeholder="Email"
                                    value={form.email}
                                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                                />
                            </div>
                            <input
                                className="appt-input"
                                placeholder="Service (optional)"
                                value={form.service}
                                onChange={(e) => setForm({ ...form, service: e.target.value })}
                            />
                            <button className="appt-btn primary" onClick={submitBooking} disabled={booking}>
                                {booking ? "Booking…" : "Confirm booking"}
                            </button>
                        </div>
                    )}
                </section>

                {/* settings */}
                <section className="appt-card">
                    <h2 className="appt-card-title"><Clock size={18} /> Availability settings</h2>

                    <div className="hours-editor">
                        {hours
                            .slice()
                            .sort((a, b) => a.weekday - b.weekday)
                            .map((h) => (
                                <div className="hours-row" key={h.weekday}>
                                    <span className="hours-day">{WEEKDAYS[h.weekday]}</span>
                                    <label className="switch">
                                        <input
                                            type="checkbox"
                                            checked={h.is_open}
                                            onChange={(e) =>
                                                setHours((prev) =>
                                                    prev.map((x) =>
                                                        x.weekday === h.weekday ? { ...x, is_open: e.target.checked } : x
                                                    )
                                                )
                                            }
                                        />
                                        <span className="slider" />
                                    </label>
                                    <input
                                        type="time"
                                        className="appt-input tiny"
                                        disabled={!h.is_open}
                                        value={h.open_time || "10:00"}
                                        onChange={(e) =>
                                            setHours((prev) =>
                                                prev.map((x) =>
                                                    x.weekday === h.weekday ? { ...x, open_time: e.target.value } : x
                                                )
                                            )
                                        }
                                    />
                                    <span className="hours-dash">–</span>
                                    <input
                                        type="time"
                                        className="appt-input tiny"
                                        disabled={!h.is_open}
                                        value={h.close_time || "18:00"}
                                        onChange={(e) =>
                                            setHours((prev) =>
                                                prev.map((x) =>
                                                    x.weekday === h.weekday ? { ...x, close_time: e.target.value } : x
                                                )
                                            )
                                        }
                                    />
                                </div>
                            ))}
                    </div>

                    {rules && (
                        <div className="rules-grid">
                            <NumField label="Slot (min)" value={rules.slot_duration_minutes}
                                onChange={(v) => setRules({ ...rules, slot_duration_minutes: v })} />
                            <NumField label="Buffer (min)" value={rules.buffer_minutes}
                                onChange={(v) => setRules({ ...rules, buffer_minutes: v })} />
                            <NumField label="Min notice (min)" value={rules.min_notice_minutes}
                                onChange={(v) => setRules({ ...rules, min_notice_minutes: v })} />
                            <NumField label="Max advance (days)" value={rules.max_advance_days}
                                onChange={(v) => setRules({ ...rules, max_advance_days: v })} />
                        </div>
                    )}

                    <button className="appt-btn primary" onClick={saveSettings} disabled={savingSettings}>
                        {savingSettings ? "Saving…" : "Save settings"}
                    </button>
                </section>
            </div>

            {/* appointments table */}
            <section className="appt-card">
                <div className="appt-card-head">
                    <h2 className="appt-card-title"><Calendar size={18} /> All appointments</h2>
                    <button className="appt-btn ghost sm" onClick={() => refreshAppointments()}>
                        <RefreshCw size={14} /> Refresh
                    </button>
                </div>

                <table className="appt-table">
                    <thead>
                        <tr>
                            <th>Customer</th>
                            <th>Service</th>
                            <th>When ({tz})</th>
                            <th>Source</th>
                            <th>Status</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {appointments.map((a) => (
                            <tr key={a.id}>
                                <td>
                                    <div className="cust">
                                        <strong>{a.customer_name || "—"}</strong>
                                        <span>{a.customer_phone || a.customer_email || ""}</span>
                                    </div>
                                </td>
                                <td>{a.service || "—"}</td>
                                <td>{fmt(a.scheduled_at, tz)}</td>
                                <td><span className="source-tag">{a.source}</span></td>
                                <td><span className={`appt-status ${a.status}`}>{a.status}</span></td>
                                <td className="actions">
                                    {a.status !== "cancelled" && (
                                        <>
                                            <button
                                                className="link-btn"
                                                onClick={() => {
                                                    setRescheduleFor(a);
                                                    setRescheduleValue(a.scheduled_at.slice(0, 16));
                                                }}
                                            >
                                                Reschedule
                                            </button>
                                            <button className="link-btn danger" onClick={() => doCancel(a)}>
                                                Cancel
                                            </button>
                                        </>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {appointments.length === 0 && (
                            <tr>
                                <td colSpan={6} className="empty">No appointments yet.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </section>

            {/* reschedule modal */}
            {rescheduleFor && (
                <div className="modal-overlay" onClick={() => setRescheduleFor(null)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <h3>Reschedule appointment</h3>
                        <p className="modal-sub">
                            {rescheduleFor.customer_name} — currently {fmt(rescheduleFor.scheduled_at, tz)}
                        </p>
                        <label className="appt-label">
                            New time ({tz})
                            <input
                                type="datetime-local"
                                className="appt-input"
                                value={rescheduleValue}
                                onChange={(e) => setRescheduleValue(e.target.value)}
                            />
                        </label>
                        <div className="modal-actions">
                            <button className="appt-btn ghost" onClick={() => setRescheduleFor(null)}>Cancel</button>
                            <button className="appt-btn primary" onClick={doReschedule}>Save new time</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
        </AppShell>
    );
}

function StatCard({ icon, label, value, tone }: {
    icon: ReactNode; label: string; value: number; tone: string;
}) {
    return (
        <div className={`appt-stat ${tone}`}>
            <div className="appt-stat-icon">{icon}</div>
            <div>
                <div className="appt-stat-value">{value}</div>
                <div className="appt-stat-label">{label}</div>
            </div>
        </div>
    );
}

function NumField({ label, value, onChange }: {
    label: string; value: number; onChange: (v: number) => void;
}) {
    return (
        <label className="appt-label">
            {label}
            <input
                type="number"
                className="appt-input"
                value={value}
                min={0}
                onChange={(e) => onChange(parseInt(e.target.value || "0", 10))}
            />
        </label>
    );
}

function GoogleCard({ google, onConnect, onDisconnect }: {
    google: GoogleStatus | null; onConnect: () => void; onDisconnect: () => void;
}) {
    return (
        <div className="google-card">
            <div className="google-left">
                <div className="google-icon"><Calendar size={20} /></div>
                <div>
                    <div className="google-title">Google Calendar</div>
                    <div className="google-sub">
                        {google?.connected
                            ? "Connected — new bookings sync to your calendar."
                            : "Sync every booking to your Google Calendar automatically."}
                    </div>
                </div>
            </div>
            <div className="google-right">
                {!google?.available && (
                    <span className="google-hint">
                        <AlertTriangle size={14} /> Not configured on server
                    </span>
                )}
                {google?.available && google?.connected && (
                    <button className="appt-btn ghost" onClick={onDisconnect}>
                        <Unlink size={15} /> Disconnect
                    </button>
                )}
                {google?.available && !google?.connected && (
                    <button className="appt-btn primary" onClick={onConnect}>
                        <Link2 size={15} /> Connect
                    </button>
                )}
            </div>
        </div>
    );
}
