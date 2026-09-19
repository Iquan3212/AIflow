// Mirrors backend/app/schemas.py's CallbackRequestOut. AIFlow never
// places a phone call itself - see backend/app/services/callback_service.py's
// module docstring: buyer requests -> AIFlow creates this record ->
// agency is notified -> a human agency staff member calls, entirely
// outside AIFlow.
export type CallbackStatus = "requested" | "assigned" | "contacted" | "completed" | "cancelled";

export interface CallbackRequest {
    id: string;
    agency_id: string;
    buyer_id: string | null;
    lead_id: string | null;
    property_id: string | null;
    phone_number: string;
    preferred_time: string | null;
    notes: string | null;
    status: CallbackStatus;
    assigned_to: string | null;
    requested_at: string;
    assigned_at: string | null;
    contacted_at: string | null;
    completed_at: string | null;
    created_at: string;
    updated_at: string;
}
