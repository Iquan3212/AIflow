export type KnowledgeDocumentStatus = "queued" | "processing" | "ready" | "failed";

export interface KnowledgeDocument {
    id: string;
    business_id: string;
    title: string;
    filename: string;
    file_type: string;
    size_bytes: number;
    status: KnowledgeDocumentStatus;
    error: string | null;
    chunk_count: number;
    created_at: string;
    updated_at: string;
}

export interface KnowledgeSearchResult {
    document_id: string;
    document_name: string;
    chunk_id: string;
    content: string;
    score: number;
}

export const KNOWLEDGE_ALLOWED_EXTENSIONS = ["pdf", "docx", "txt"] as const;
export const KNOWLEDGE_MAX_UPLOAD_BYTES = 15 * 1024 * 1024;
