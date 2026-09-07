import api from "./api";

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
