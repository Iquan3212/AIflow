export type LeadStatus = "new" | "contacted" | "qualified" | "converted" | "lost";

export interface Lead {
    id: string;
    name: string | null;
    phone: string | null;
    email: string | null;
    service_interested: string | null;
    budget: string | null;
    status: LeadStatus;
    created_at: string;
    updated_at?: string;
}

export interface LeadCreateInput {
    name?: string;
    phone?: string;
    email?: string;
    service_interested?: string;
    budget?: string;
}

export const LEAD_STATUSES: LeadStatus[] = ["new", "contacted", "qualified", "converted", "lost"];
