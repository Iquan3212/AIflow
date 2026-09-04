import api from "./api";
import type { SupportTicket, TicketPriority, TicketStatus } from "../types/supportTicket";

export async function listTickets(status?: TicketStatus): Promise<SupportTicket[]> {
    const response = await api.get<SupportTicket[]>("/support-tickets/", {
        params: status ? { status } : undefined,
    });
    return response.data;
}

export async function updateTicket(
    id: string,
    payload: { status?: TicketStatus; priority?: TicketPriority }
): Promise<SupportTicket> {
    const response = await api.patch<SupportTicket>(`/support-tickets/${id}`, payload);
    return response.data;
}

export async function deleteTicket(id: string): Promise<void> {
    await api.delete(`/support-tickets/${id}`);
}
