// Mirrors backend/app/schemas.py's BuyerProfileOut/BuyerProfileUpdate
// (Buyer UI phase). Preferences/notification fields are new, additive
// columns on Buyer - all optional, opt-out-by-design.

import type { Furnishing, PropertyType } from "./marketplace";

export interface BuyerProfile {
    id: string;
    name: string | null;
    email: string;
    phone: string | null;
    preferred_city: string | null;
    preferred_locality: string | null;
    preferred_bhk: number | null;
    budget_min: string | null;
    budget_max: string | null;
    preferred_property_type: PropertyType | null;
    preferred_furnishing: Furnishing | null;
    notify_site_visit_updates: boolean;
    notify_inquiry_updates: boolean;
    notify_booking_updates: boolean;
    notify_property_alerts: boolean;
    created_at: string;
}

export type BuyerProfileUpdate = Partial<
    Pick<
        BuyerProfile,
        | "name"
        | "phone"
        | "preferred_city"
        | "preferred_locality"
        | "preferred_bhk"
        | "preferred_property_type"
        | "preferred_furnishing"
        | "notify_site_visit_updates"
        | "notify_inquiry_updates"
        | "notify_booking_updates"
        | "notify_property_alerts"
    >
> & {
    budget_min?: number | string | null;
    budget_max?: number | string | null;
};
