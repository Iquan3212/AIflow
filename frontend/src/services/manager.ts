import api from "./api";
import type { ConversationMessage, ManagerChatResponse } from "../types/ai";

interface RawMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface ConversationResponse {
  conversation_id: string;
  messages: ConversationMessage[];
}

export async function chatManager(message: string, conversationId?: string): Promise<ManagerChatResponse> {
  const response = await api.post<ManagerChatResponse>("/manager/chat", {
    message,
    conversation_id: conversationId ?? null,
  });
  return response.data;
}

export async function getConversation(conversationId?: string): Promise<ConversationResponse> {
  const response = await api.get<{ conversation_id: string; messages: RawMessage[] }>("/manager/conversation", {
    params: conversationId ? { conversation_id: conversationId } : undefined,
  });
  return {
    conversation_id: response.data.conversation_id,
    messages: response.data.messages.map((m) => ({
      role: m.role,
      content: m.content,
      timestamp: m.created_at,
    })),
  };
}

export async function getManagerStatus() {
  const response = await api.get("/manager/status");
  return response.data;
}
