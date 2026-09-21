import api from "./api";
import type { AgencyNotification } from "../types/notification";

export async function listNotifications(
    params: { unreadOnly?: boolean; limit?: number; offset?: number } = {}
): Promise<AgencyNotification[]> {
    const response = await api.get<AgencyNotification[]>("/notifications", {
        params: {
            unread_only: params.unreadOnly ?? false,
            limit: params.limit ?? 50,
            offset: params.offset ?? 0,
        },
    });
    return response.data;
}

export async function getUnreadNotificationCount(): Promise<number> {
    const response = await api.get<{ unread_count: number }>("/notifications/unread-count");
    return response.data.unread_count;
}

export async function markNotificationRead(id: string): Promise<AgencyNotification> {
    const response = await api.post<AgencyNotification>(`/notifications/${id}/read`);
    return response.data;
}

export async function markAllNotificationsRead(): Promise<void> {
    await api.post("/notifications/read-all");
}

export interface NotificationPreferenceItem {
    event_type: string;
    event_label: string;
    channel: string;
    enabled: boolean;
}

export interface NotificationPreferenceUpdate {
    event_type: string;
    channel: string;
    enabled: boolean;
}

export async function getNotificationPreferences(): Promise<NotificationPreferenceItem[]> {
    const response = await api.get<NotificationPreferenceItem[]>("/notifications/preferences");
    return response.data;
}

export async function updateNotificationPreferences(
    updates: NotificationPreferenceUpdate[]
): Promise<NotificationPreferenceItem[]> {
    const response = await api.put<NotificationPreferenceItem[]>("/notifications/preferences", { updates });
    return response.data;
}
