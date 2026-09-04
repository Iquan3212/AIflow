export type DraftKind = "quotation" | "campaign";
export type DraftStatus = "draft" | "sent" | "archived";

export interface AIDraft {
    id: string;
    business_id: string;
    lead_id: string | null;
    kind: DraftKind;
    title: string | null;
    content: string;
    status: DraftStatus;
    created_at: string;
    updated_at: string;
}

export const DRAFT_STATUSES: DraftStatus[] = ["draft", "sent", "archived"];
