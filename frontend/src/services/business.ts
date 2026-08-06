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

export async function getCurrentBusiness(): Promise<Business> {
    const response = await api.get("/businesses/me");
    return response.data;
}