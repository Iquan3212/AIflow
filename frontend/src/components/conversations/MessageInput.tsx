import { useState } from "react";
import { Send } from "lucide-react";

import Button from "../ui/Button";

type Props = {
    onSend: (message: string) => void;
};

export default function MessageInput({ onSend }: Props) {
    const [message, setMessage] = useState("");

    function handleSend() {
        if (!message.trim()) return;

        onSend(message);
        setMessage("");
    }

    return (
        <div className="border-t border-slate-100 p-4 flex gap-3">
            <label htmlFor="conversation-message" className="sr-only">
                Message
            </label>
            <input
                id="conversation-message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === "Enter") {
                        handleSend();
                    }
                }}
                placeholder="Type your message…"
                className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none transition-colors focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
            />

            <Button onClick={handleSend} aria-label="Send message">
                <Send size={16} />
                Send
            </Button>
        </div>
    );
}
