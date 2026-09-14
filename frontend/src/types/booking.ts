// Mirrors backend/app/schemas.py's Phase 9 Booking schemas. A Booking
// is the commercial conversion of a unit - a distinct concept from
// Appointment (a site visit is a meeting; a Booking is a sale).

export type BookingStatus = "initiated" | "pending" | "confirmed" | "completed" | "cancelled";

export const BOOKING_STATUSES: BookingStatus[] = ["initiated", "pending", "confirmed", "completed", "cancelled"];

// The exact transitions backend/app/services/marketplace/booking_service.py
// validates - the UI only ever offers one of these, never a status that
// would just 409.
export const ALLOWED_BOOKING_TRANSITIONS: Record<BookingStatus, BookingStatus[]> = {
    initiated: ["pending", "cancelled"],
    pending: ["confirmed", "cancelled"],
    confirmed: ["completed", "cancelled"],
    completed: [],
    cancelled: [],
};

export interface BookingPropertySummary {
    id: string;
    project_id: string;
    project_name: string;
    unit_number: string | null;
    building: string | null;
    property_type: string;
    bhk: number | null;
    price: string | null;
}

export interface Booking {
    id: string;
    agency_id: string;
    property_id: string | null;
    buyer_id: string | null;
    lead_id: string | null;
    appointment_id: string | null;
    status: BookingStatus;
    agreed_price: string | null;
    notes: string | null;
    created_at: string;
    updated_at: string;
    property: BookingPropertySummary | null;
}

export interface BookingCreateInput {
    property_id: string;
    buyer_id?: string;
    lead_id?: string;
    appointment_id?: string;
    agreed_price?: number;
    notes?: string;
}
