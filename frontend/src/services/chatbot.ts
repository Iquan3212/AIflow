import api from "./api";

import type { ChatbotConfig } from "../types/chatbot";

export async function getChatbotConfig(): Promise<ChatbotConfig> {

    const response = await api.get(
        "/agencies/me/chatbot-config"
    );

    return response.data;
}

export async function updateChatbotConfig(
    payload: Partial<ChatbotConfig>
) {

    const response = await api.put(
        "/agencies/me/chatbot-config",
        payload
    );

    return response.data;
}
