export interface Message {
    sender: "user" | "ai";
    text: string;
}

export interface Conversation {
    id: string;
    channel: string;
    /** Real customer name captured via the Lead linked to this conversation
     * - null until the customer has actually given it. */
    customer_name: string | null;
    /** Display label: customer_name once known, otherwise a readable
     * stand-in for the anonymous visitor. Never the raw visitor_id/UUID. */
    name: string;
    phone: string;
    total_messages: number;
    last_message: string | null;
    created_at: string | null;
    updated_at: string | null;
    messages: Message[];
}
