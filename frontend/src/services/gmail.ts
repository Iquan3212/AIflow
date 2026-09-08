import api from "./api";

export type GmailSendMode = "read_only" | "approval_required" | "automated";

export interface GmailStatus {
    available: boolean;
    connected: boolean;
    google_email: string | null;
    send_mode: GmailSendMode;
}

export interface GmailPendingAction {
    id: string;
    conversation_id: string | null;
    employee: string | null;
    action_type: string;
    to_address: string;
    subject: string;
    body: string;
    status: "pending" | "approved" | "rejected" | "sent" | "failed";
    gmail_message_id: string | null;
    error: string | null;
    created_at: string;
    decided_at: string | null;
}

export async function getGmailStatus(): Promise<GmailStatus> {
    const res = await api.get<GmailStatus>("/gmail/status");
    return res.data;
}

export async function getGmailConnectUrl(): Promise<string> {
    const res = await api.get<{ url: string }>("/gmail/connect");
    return res.data.url;
}

export async function disconnectGmail(): Promise<void> {
    await api.delete("/gmail");
}

export async function setGmailSendMode(send_mode: GmailSendMode): Promise<GmailStatus> {
    const res = await api.patch<GmailStatus>("/gmail/mode", { send_mode });
    return res.data;
}

export async function listGmailPending(status?: string): Promise<GmailPendingAction[]> {
    const res = await api.get<GmailPendingAction[]>("/gmail/pending", { params: status ? { status } : undefined });
    return res.data;
}

export async function approveGmailPending(id: string): Promise<{ ok: boolean; status?: string; gmail_message_id?: string }> {
    const res = await api.post(`/gmail/pending/${encodeURIComponent(id)}/approve`);
    return res.data;
}

export async function rejectGmailPending(id: string): Promise<{ ok: boolean; status?: string }> {
    const res = await api.post(`/gmail/pending/${encodeURIComponent(id)}/reject`);
    return res.data;
}
