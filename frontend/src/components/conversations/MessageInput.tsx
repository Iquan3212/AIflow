import { useState } from "react";

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
        <div className="border-t p-5 flex gap-4">

            <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === "Enter") {
                        handleSend();
                    }
                }}
                placeholder="Type your message..."
                className="flex-1 border rounded-xl px-5 py-3 outline-none"
            />

            <button
                onClick={handleSend}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 rounded-xl"
            >
                Send
            </button>

        </div>
    );
}