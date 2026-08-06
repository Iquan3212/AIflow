import api from "./api";

export interface EmployeeMessage {
    role: "user" | "assistant";
    content: string;
    created_at?: string;
}

export interface EmployeeConversation {
    conversation_id: string;
    messages: EmployeeMessage[];
}

export interface EmployeeReply {
    conversation_id: string;
    reply: string;
    intent: string;
    tool: string | null;
    confidence: number;
}

export async function getEmployeeConversation(
    conversationId?: string,
): Promise<EmployeeConversation> {
    const response = await api.get("/employee/conversation", {
        params: conversationId ? { conversation_id: conversationId } : undefined,
    });
    return response.data;
}

export async function chatWithEmployee(
    message: string,
    conversationId?: string,
): Promise<EmployeeReply> {
    const response = await api.post("/employee/chat", {
        message,
        conversation_id: conversationId ?? null,
    });
    return response.data;
}
