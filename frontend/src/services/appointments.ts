import api from "./api";

export interface Appointment {
    id: string;
    business_id: string;
    lead_id: string | null;
    conversation_id: string | null;
    customer_name: string | null;
    customer_phone: string | null;
    customer_email: string | null;
    service: string | null;
    scheduled_at: string; // UTC ISO
    end_at: string;       // UTC ISO
    duration_minutes: number;
    status: string;
    source: string;
    calendar_provider: string | null;
    calendar_event_id: string | null;
    reminder_sent_at: string | null;
    created_at: string;
}

export interface Slot {
    start_local_iso: string; // "YYYY-MM-DDTHH:MM" in business timezone
    label: string;           // humanized
}

export interface Availability {
    date_local: string;
    timezone: string;
    slots: Slot[];
}

export interface BusinessHoursItem {
    weekday: number; // 0=Mon .. 6=Sun
    is_open: boolean;
    open_time: string | null;  // "HH:MM"
    close_time: string | null; // "HH:MM"
}

export interface SchedulingRules {
    slot_duration_minutes: number;
    buffer_minutes: number;
    min_notice_minutes: number;
    max_advance_days: number;
    reminder_offsets_hours: number[];
}

export interface NewAppointment {
    start_local_iso: string;
    customer_name: string;
    customer_phone?: string;
    customer_email?: string;
    service?: string;
}

// ---- appointments -------------------------------------------------------

export async function listAppointments(): Promise<Appointment[]> {
    const res = await api.get("/appointments/");
    return res.data;
}

export async function getAvailability(dateLocal: string): Promise<Availability> {
    const res = await api.get("/appointments/availability", {
        params: { date_local: dateLocal },
    });
    return res.data;
}

export async function bookAppointment(payload: NewAppointment): Promise<Appointment> {
    const res = await api.post("/appointments/", payload);
    return res.data;
}

export async function rescheduleAppointment(id: string, newStartLocalIso: string): Promise<Appointment> {
    const res = await api.put(`/appointments/${id}/reschedule`, {
        new_start_local_iso: newStartLocalIso,
    });
    return res.data;
}

export async function cancelAppointment(id: string): Promise<void> {
    await api.delete(`/appointments/${id}`);
}

// ---- settings -----------------------------------------------------------

export async function getHours(): Promise<BusinessHoursItem[]> {
    const res = await api.get("/appointments/settings/hours");
    return res.data;
}

export async function updateHours(hours: BusinessHoursItem[]): Promise<BusinessHoursItem[]> {
    const res = await api.put("/appointments/settings/hours", { hours });
    return res.data;
}

export async function getRules(): Promise<SchedulingRules> {
    const res = await api.get("/appointments/settings/rules");
    return res.data;
}

export async function updateRules(rules: Partial<SchedulingRules>): Promise<SchedulingRules> {
    const res = await api.put("/appointments/settings/rules", rules);
    return res.data;
}

// ---- google calendar ----------------------------------------------------

export interface GoogleStatus {
    provider: string;
    available: boolean;
    connected: boolean;
}

export async function getGoogleStatus(): Promise<GoogleStatus> {
    const res = await api.get("/integrations/google/status");
    return res.data;
}

export async function getGoogleConnectUrl(): Promise<string> {
    const res = await api.get("/integrations/google/connect");
    return res.data.url;
}

export async function disconnectGoogle(): Promise<void> {
    await api.delete("/integrations/google");
}
