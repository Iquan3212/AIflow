import api from "./api";

export interface Agency {
    id: string;
    name: string;
    slug: string;
    industry: string | null;
    contact_email: string;
    plan: string;
    timezone: string;
    brand_color: string;
    created_at: string;
}

export interface AgencyUpdateInput {
    name?: string;
    industry?: string;
    timezone?: string;
}

export async function getCurrentAgency(): Promise<Agency> {
    const response = await api.get<Agency>("/agencies/me");
    return response.data;
}

export async function updateCurrentAgency(payload: AgencyUpdateInput): Promise<Agency> {
    const response = await api.patch<Agency>("/agencies/me", payload);
    return response.data;
}