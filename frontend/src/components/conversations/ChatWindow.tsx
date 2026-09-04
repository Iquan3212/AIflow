import { useEffect, useRef, useState } from "react";

import MessageBubble from "./MessageBubble";
import MessageInput from "./MessageInput";

import { sendMessage } from "../../services/conversation";
import { getErrorMessage } from "../../services/api";

import type { Conversation } from "../../types/conversation";
import { useBusiness } from "../../context/BusinessContext";

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

export default function ChatWindow({
    conversation,
    onMessageSent,
}: Props) {
    const { business } = useBusiness();

    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const bottomRef = useRef<HTMLDivElement>(null);

    const messages = conversation?.messages ?? [];

    useEffect(() => {

        bottomRef.current?.scrollIntoView({
            behavior: "smooth",
        });

    }, [messages.length]);

    async function handleSend(text: string) {

        if (!business?.slug) {
            setError("Business context is unavailable");
            return;
        }

        setError(null);
        setSending(true);

        try {

            const response = await sendMessage(text, business.slug, conversation?.id);

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

        <div className="bg-white rounded-2xl shadow h-full flex flex-col">

            <div className="border-b px-6 py-5">

                <h2 className="font-bold text-xl">

                    {
                        conversation
                            ? conversation.name
                            : "New Conversation"
                    }

                </h2>

                <p className="text-gray-500 text-sm">

                    AI Workforce

                </p>

            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">

                {
                    messages.length === 0 && !sending && (

                        <div className="text-center text-gray-400 mt-16">

                            <h2 className="text-2xl font-semibold">

                                👋 Welcome

                            </h2>

                            <p className="mt-3">

                                Start a conversation with your AI Workforce.

                            </p>

                        </div>

                    )
                }

                {

                    messages.map((message, index) => (

                        <MessageBubble

                            key={index}

                            message={message}

                        />

                    ))

                }

                {error && (
                    <p className="text-sm text-red-500">{error}</p>
                )}

                {

                    sending && (

                        <div className="text-sm text-gray-500">

                            AI is typing...

                        </div>

                    )

                }

                <div ref={bottomRef} />

            </div>

            <MessageInput

                onSend={handleSend}

            />

        </div>

    );

}
