export interface Message {
    sender: "user" | "ai";
    text: string;
}

export interface Conversation {
    id: string;
    name: string;
    phone: string;
    messages: Message[];
}