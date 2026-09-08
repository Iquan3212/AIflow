import api from "./api";
import type { KnowledgeDocument, KnowledgeSearchResult } from "../types/knowledge";

export async function listKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
    const response = await api.get<KnowledgeDocument[]>("/knowledge/documents");
    return response.data;
}

export async function uploadKnowledgeDocument(file: File): Promise<KnowledgeDocument> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post<KnowledgeDocument>("/knowledge/documents", formData);
    return response.data;
}

export async function retryKnowledgeDocument(id: string): Promise<KnowledgeDocument> {
    const response = await api.post<KnowledgeDocument>(`/knowledge/documents/${id}/retry`);
    return response.data;
}

export async function deleteKnowledgeDocument(id: string): Promise<void> {
    await api.delete(`/knowledge/documents/${id}`);
}

export async function searchKnowledge(query: string, topK = 4): Promise<KnowledgeSearchResult[]> {
    const response = await api.post<KnowledgeSearchResult[]>("/knowledge/search", { query, top_k: topK });
    return response.data;
}
