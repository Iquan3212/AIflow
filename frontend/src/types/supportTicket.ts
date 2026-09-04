export type TicketPriority = "normal" | "high";
export type TicketStatus = "open" | "in_progress" | "resolved" | "closed";

export interface SupportTicket {
    id: string;
    business_id: string;
    lead_id: string | null;
    issue_summary: string;
    priority: TicketPriority;
    status: TicketStatus;
    created_at: string;
    updated_at: string;
}

export const TICKET_STATUSES: TicketStatus[] = ["open", "in_progress", "resolved", "closed"];
export const TICKET_PRIORITIES: TicketPriority[] = ["normal", "high"];
