import { Bot, User } from "lucide-react";
import type { Message } from "../../types/conversation";

type Props = {
    message: Message;
};

export default function MessageBubble({ message }: Props) {
    const isUser = message.sender === "user";

    return (
        <div className={`flex items-end gap-2 mb-4 ${isUser ? "justify-end" : "justify-start"}`}>
            {!isUser && (
                <div
                    className="w-7 h-7 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center shrink-0"
                    aria-hidden="true"
                >
                    <Bot size={14} />
                </div>
            )}

            <div
                className={`rounded-2xl px-4 py-2.5 max-w-md text-sm leading-relaxed ${
                    isUser
                        ? "bg-brand-600 text-white rounded-br-md"
                        : "bg-slate-100 text-slate-800 rounded-bl-md"
                }`}
            >
                <span className="sr-only">{isUser ? "Customer: " : "AI: "}</span>
                {message.text}
            </div>

            {isUser && (
                <div
                    className="w-7 h-7 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center shrink-0"
                    aria-hidden="true"
                >
                    <User size={14} />
                </div>
            )}
        </div>
    );
}
