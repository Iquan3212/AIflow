import api from "./api";
import type { CallbackRequest } from "../types/callback";

export async function listCallbacks(): Promise<CallbackRequest[]> {
    const response = await api.get<CallbackRequest[]>("/callbacks");
    return response.data;
}

export async function assignCallback(id: string, assignedToUserId?: string): Promise<CallbackRequest> {
    const response = await api.post<CallbackRequest>(`/callbacks/${id}/assign`, {
        assigned_to_user_id: assignedToUserId ?? null,
    });
    return response.data;
}

export async function markCallbackContacted(id: string): Promise<CallbackRequest> {
    const response = await api.post<CallbackRequest>(`/callbacks/${id}/contacted`);
    return response.data;
}

export async function completeCallback(id: string): Promise<CallbackRequest> {
    const response = await api.post<CallbackRequest>(`/callbacks/${id}/complete`);
    return response.data;
}

export async function cancelCallback(id: string): Promise<CallbackRequest> {
    const response = await api.post<CallbackRequest>(`/callbacks/${id}/cancel`);
    return response.data;
}
