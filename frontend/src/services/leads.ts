import api from "./api";
import type { Lead, LeadCreateInput, LeadStatus } from "../types/lead";

export async function listLeads(): Promise<Lead[]> {
    const response = await api.get<Lead[]>("/leads/");
    return response.data;
}

export async function createLead(payload: LeadCreateInput): Promise<Lead> {
    const response = await api.post<Lead>("/leads/", payload);
    return response.data;
}

export async function updateLeadStatus(id: string, status: LeadStatus): Promise<Lead> {
    const response = await api.put<Lead>(`/leads/${id}`, { status });
    return response.data;
}

export async function deleteLead(id: string): Promise<void> {
    await api.delete(`/leads/${id}`);
}
