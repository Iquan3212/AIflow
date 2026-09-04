import api from "./api";

export interface Session {
    id: string;
    device_name: string | null;
    ip_address: string | null;
    created_at: string;
    last_used_at: string;
}

export async function listSessions(): Promise<Session[]> {
    const response = await api.get<Session[]>("/auth/sessions");
    return response.data;
}

export async function revokeSession(id: string): Promise<void> {
    await api.delete(`/auth/sessions/${id}`);
}
