import api from "./api";
import type { AIDraft, DraftKind, DraftStatus } from "../types/draft";

export async function listDrafts(kind?: DraftKind): Promise<AIDraft[]> {
    const response = await api.get<AIDraft[]>("/drafts/", { params: kind ? { kind } : undefined });
    return response.data;
}

export async function updateDraftStatus(id: string, status: DraftStatus): Promise<AIDraft> {
    const response = await api.patch<AIDraft>(`/drafts/${id}`, { status });
    return response.data;
}

export async function deleteDraft(id: string): Promise<void> {
    await api.delete(`/drafts/${id}`);
}
