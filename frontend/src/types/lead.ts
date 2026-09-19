import type { CallbackRequest } from "./callback";

// Phase 9 extends this vocabulary additively (site_visit_scheduled,
// visited, negotiating) - the original 5 values and their meaning are
// unchanged; see backend app/models.py's Lead.status comment and
// app/services/marketplace/lead_lifecycle.py.
export type LeadStatus =
    | "new" | "contacted" | "qualified"
    | "site_visit_scheduled" | "visited" | "negotiating"
    | "converted" | "lost";

export interface LeadPropertySummary {
    id: string;
    project_id: string;
    project_name: string;
    unit_number: string | null;
    building: string | null;
    property_type: string;
    bhk: number | null;
    price: string | null;
}

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
    // Phase 9: present only for marketplace-originated leads.
    buyer_id?: string | null;
    property_id?: string | null;
    property?: LeadPropertySummary | null;
    callback_request?: CallbackRequest | null;
}

export interface LeadCreateInput {
    name?: string;
    phone?: string;
    email?: string;
    service_interested?: string;
    budget?: string;
}

export const LEAD_STATUSES: LeadStatus[] = [
    "new", "contacted", "qualified", "site_visit_scheduled", "visited", "negotiating", "converted", "lost",
];
