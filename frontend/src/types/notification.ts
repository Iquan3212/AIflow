// Mirrors backend/app/schemas.py's NotificationOut. The two real types
// the backend actually creates today - see app/models.py's
// NotificationType. Never render a type this list doesn't have (no
// fabricated notification kinds not backed by a real backend event).
export type NotificationType = "new_lead" | "callback_requested";

export interface AgencyNotification {
    id: string;
    type: NotificationType;
    title: string;
    message: string;
    lead_id: string | null;
    callback_request_id: string | null;
    read_at: string | null;
    created_at: string;
}
