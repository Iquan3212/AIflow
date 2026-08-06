import api from "./api";

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

export async function getConversations() {

    // Auth-based now: the backend returns the authenticated business's
    // conversations from the token, so no slug is passed from the client.
    const response = await api.get("/conversation");

    return response.data;

}

export async function sendMessage(
    message: string,
    businessSlug: string,
    conversationId?: string,
) {

    const response = await api.post(
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
