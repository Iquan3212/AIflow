import { useEffect, useRef, useState } from "react";
import { MessageSquare } from "lucide-react";

import MessageBubble from "./MessageBubble";
import MessageInput from "./MessageInput";

import { sendMessage } from "../../services/conversation";
import { getErrorMessage } from "../../services/api";
import { ChannelBadge } from "./ConversationList";

import type { Conversation } from "../../types/conversation";
import { useAgency } from "../../context/AgencyContext";

type Props = {
    conversation: Conversation | null;
    /** Called after a message round-trip completes, with the (possibly
     * newly created) conversation's id - the parent re-fetches the list and
     * re-selects that conversation, so this component never keeps its own
     * copy of the message history. That's the fix for the bug where the
     * chat panel and the Customer Details panel disagreed: previously this
     * component tracked its own `messages` state that only synced from the
     * conversation prop once, on selection, and diverged from then on. */
    onMessageSent: (conversationId: string) => Promise<void>;
};

export default function ChatWindow({ conversation, onMessageSent }: Props) {
    const { agency } = useAgency();

    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const bottomRef = useRef<HTMLDivElement>(null);

    const messages = conversation?.messages ?? [];

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages.length]);

    async function handleSend(text: string) {
        if (!agency?.slug) {
            setError("Agency context is unavailable");
            return;
        }

        setError(null);
        setSending(true);

        try {
            const response = await sendMessage(text, agency.slug, conversation?.id);

            // The conversation prop is the single source of truth for
            // messages/customer info - refresh it rather than keeping a
            // local copy that could drift from what Customer Details shows.
            await onMessageSent(response.conversation_id);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSending(false);
        }
    }

    return (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-soft h-full flex flex-col">
            <div className="border-b border-slate-100 px-5 py-4 flex items-center justify-between gap-3">
                <div className="min-w-0">
                    <h2 className="font-display font-semibold text-slate-900 truncate">
                        {conversation ? conversation.name : "New Conversation"}
                    </h2>
                    <p className="text-slate-500 text-xs mt-0.5">AI Workforce</p>
                </div>

                {conversation && <ChannelBadge channel={conversation.channel} />}
            </div>

            <div className="flex-1 overflow-y-auto p-5 thin-scrollbar">
                {messages.length === 0 && !sending && (
                    <div className="flex flex-col items-center justify-center text-center py-16">
                        <div className="w-14 h-14 rounded-2xl bg-brand-50 text-brand-500 flex items-center justify-center mb-3">
                            <MessageSquare size={24} aria-hidden="true" />
                        </div>
                        <h2 className="text-lg font-display font-semibold text-slate-800">Welcome</h2>
                        <p className="mt-2 text-sm text-slate-400 max-w-xs">
                            Start a conversation with your AI Workforce.
                        </p>
                    </div>
                )}

                {messages.map((message, index) => (
                    <MessageBubble key={index} message={message} />
                ))}

                {error && (
                    <p className="text-sm text-red-600" role="alert">
                        {error}
                    </p>
                )}

                {sending && (
                    <div className="flex items-center gap-1.5 text-sm text-slate-400 ml-9" role="status" aria-live="polite">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-bounce [animation-delay:-0.2s]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-bounce [animation-delay:-0.1s]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-bounce" />
                    </div>
                )}

                <div ref={bottomRef} />
            </div>

            <MessageInput onSend={handleSend} />
        </div>
    );
}
