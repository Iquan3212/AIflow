import { useEffect, useRef, useState } from "react";
import { Bot, Send } from "lucide-react";

import Layout from "../../components/dashboard/Layout";
import { useBusiness } from "../../context/BusinessContext";
import {
    chatWithEmployee,
    getEmployeeConversation,
    type EmployeeMessage,
} from "../../services/employee";

const EMPTY_GREETING: EmployeeMessage = {
    role: "assistant",
    content: "Hi! I’m your AI Employee. I can review leads, check the calendar, capture a lead, or book an appointment for you.",
};

export default function Employee() {
    const { business } = useBusiness();
    const [messages, setMessages] = useState<EmployeeMessage[]>([]);
    const [conversationId, setConversationId] = useState<string>();
    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(true);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        async function loadHistory() {
            try {
                const data = await getEmployeeConversation();
                setConversationId(data.conversation_id);
                setMessages(data.messages);
            } catch (error) {
                console.error("Failed to load AI Employee history", error);
            } finally {
                setLoadingHistory(false);
            }
        }
        loadHistory();
    }, []);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, loading]);

    async function sendMessage() {
        const content = message.trim();
        if (!content || loading) return;

        setMessages((previous) => [...previous, { role: "user", content }]);
        setMessage("");
        setLoading(true);
        try {
            const reply = await chatWithEmployee(content, conversationId);
            setConversationId(reply.conversation_id);
            setMessages((previous) => [...previous, { role: "assistant", content: reply.reply }]);
        } catch (error) {
            console.error("Failed to contact AI Employee", error);
            setMessages((previous) => [...previous, {
                role: "assistant",
                content: "I couldn’t complete that request. Please try again in a moment.",
            }]);
        } finally {
            setLoading(false);
        }
    }

    const visibleMessages = messages.length ? messages : [EMPTY_GREETING];

    return (
        <Layout>
            <div className="max-w-5xl mx-auto h-full flex flex-col">
                <div className="mb-6">
                    <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-blue-600 text-white p-3"><Bot size={26} /></div>
                        <div>
                            <h1 className="text-3xl font-bold text-slate-900">AI Employee</h1>
                            <p className="text-slate-500">Private assistant for {business?.name || "your business"}</p>
                        </div>
                    </div>
                </div>

                <section className="bg-white rounded-2xl shadow-sm border border-slate-200 flex-1 min-h-[560px] flex flex-col">
                    <div className="px-6 py-4 border-b flex items-center justify-between">
                        <div>
                            <h2 className="font-semibold">Business copilot</h2>
                            <p className="text-sm text-slate-500">Leads, appointments, availability, and live dashboard data</p>
                        </div>
                        <span className="text-sm font-medium text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full">Online</span>
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50">
                        {loadingHistory ? <p className="text-sm text-slate-400">Loading conversation…</p> : visibleMessages.map((item, index) => (
                            <div key={`${item.role}-${index}`} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
                                <div className={`max-w-[78%] rounded-2xl px-4 py-3 whitespace-pre-wrap ${item.role === "user" ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-800"}`}>
                                    {item.content}
                                </div>
                            </div>
                        ))}
                        {loading && <div className="text-sm text-slate-500">AI Employee is working…</div>}
                        <div ref={bottomRef} />
                    </div>

                    <div className="p-4 border-t flex gap-3">
                        <textarea
                            rows={2}
                            value={message}
                            onChange={(event) => setMessage(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === "Enter" && !event.shiftKey) {
                                    event.preventDefault();
                                    void sendMessage();
                                }
                            }}
                            placeholder="Ask about leads, appointments, or your business…"
                            className="flex-1 border rounded-xl px-4 py-3 resize-none outline-none focus:border-blue-500"
                            disabled={loading}
                        />
                        <button onClick={() => void sendMessage()} disabled={loading || !message.trim()} className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-5 disabled:opacity-50">
                            <Send size={20} />
                        </button>
                    </div>
                </section>
            </div>
        </Layout>
    );
}
