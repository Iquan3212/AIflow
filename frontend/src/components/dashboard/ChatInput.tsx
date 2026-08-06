import { Send } from "lucide-react";
import { useState } from "react";

export default function ChatInput() {
    const [message, setMessage] = useState("");

    function handleSend() {
        if (!message.trim()) return;

        console.log(message);

        setMessage("");
    }

    return (
        <div className="flex gap-4 mt-6">
            <input
                value={message}
                onChange={(e) =>
                    setMessage(e.target.value)
                }
                placeholder="Type a message..."
                className="flex-1 border rounded-xl px-5 py-4 outline-none"
            />

            <button
                onClick={handleSend}
                className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-6 flex items-center gap-2"
            >
                <Send size={18} />

                Send
            </button>
        </div>
    );
}