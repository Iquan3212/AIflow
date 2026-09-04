import api from "./api";
import type { Conversation } from "../types/conversation";

const VISITOR_KEY = "aiflow_visitor_id";

function getVisitorId() {

    let visitorId = localStorage.getItem(VISITOR_KEY);

    if (!visitorId) {

        visitorId = crypto.randomUUID();

        localStorage.setItem(
            VISITOR_KEY,
            visitorId,
        );

    }

    return visitorId;

}

export interface SendMessageResponse {
    conversation_id: string;
    reply: string;
}

export async function getConversations(): Promise<Conversation[]> {

    // Auth-based now: the backend returns the authenticated business's
    // conversations from the token, so no slug is passed from the client.
    const response = await api.get<Conversation[]>("/conversation/");

    return response.data;

}

export async function sendMessage(
    message: string,
    businessSlug: string,
    conversationId?: string,
): Promise<SendMessageResponse> {

    const response = await api.post<SendMessageResponse>(
        "/conversation/send",
        {

            business_slug: businessSlug,

            visitor_id: getVisitorId(),

            conversation_id:
                conversationId ?? null,

            message,

        }
    );

    return response.data;

}
