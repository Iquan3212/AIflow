import api from "./api";

export interface Business {
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

export interface BusinessUpdateInput {
    name?: string;
    industry?: string;
    timezone?: string;
}

export async function getCurrentBusiness(): Promise<Business> {
    const response = await api.get<Business>("/businesses/me");
    return response.data;
}

export async function updateCurrentBusiness(payload: BusinessUpdateInput): Promise<Business> {
    const response = await api.patch<Business>("/businesses/me", payload);
    return response.data;
}