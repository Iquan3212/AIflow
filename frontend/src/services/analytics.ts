import api from "./api";

export interface AnalyticsSeriesPoint {
    date: string;
    count: number;
}

export interface AnalyticsOverview {
    leads_by_status: Record<string, number>;
    appointments_by_status: Record<string, number>;
    leads_per_day: AnalyticsSeriesPoint[];
    appointments_per_day: AnalyticsSeriesPoint[];
    conversations_per_day: AnalyticsSeriesPoint[];
    total_leads: number;
    total_appointments: number;
    total_conversations: number;
}

export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
    const response = await api.get<AnalyticsOverview>("/analytics/overview");
    return response.data;
}
