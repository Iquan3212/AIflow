import api from "./api";
import type { ManagerChatResponse } from "../types/ai";

export async function chatManager(
  message: string,
  conversationId?: string
): Promise<ManagerChatResponse> {
  const response = await api.post("/manager/chat", {
    message,
    conversation_id: conversationId ?? null,
  });

  return response.data;
}

export async function getConversation(
  conversationId?: string
) {
  const response = await api.get("/manager/conversation", {
    params: conversationId
      ? { conversation_id: conversationId }
      : undefined,
  });

  return response.data;
}

export async function getManagerStatus() {
  const response = await api.get("/manager/status");
  return response.data;
}

export async function updateManagerSettings(
  payload: Record<string, unknown>
) {
  const response = await api.patch(
    "/manager/settings",
    payload
  );

  return response.data;
}