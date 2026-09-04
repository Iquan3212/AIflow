import api from "./api";

export interface DashboardStats {
    today_chats: number;
    new_leads_today: number;
    total_leads: number;
    upcoming_appointments: number;
    avg_response_time_seconds: number | null;
    model: string;
}

export async function getDashboardStats(): Promise<DashboardStats> {
    const response = await api.get<DashboardStats>("/dashboard/stats");
    return response.data;
}
