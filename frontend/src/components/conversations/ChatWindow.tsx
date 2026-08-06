import { useEffect, useRef, useState } from "react";

import MessageBubble from "./MessageBubble";
import MessageInput from "./MessageInput";

import {
    sendMessage,
} from "../../services/conversation";

import type {
    Conversation,
    Message,
} from "../../types/conversation";
import { useBusiness } from "../../context/BusinessContext";

type Props = {
    conversation: Conversation | null;
    refreshConversations: () => Promise<void>;
};

export default function ChatWindow({
    conversation,
    refreshConversations,
}: Props) {
    const { business } = useBusiness();

    const [messages, setMessages] = useState<Message[]>([]);
    const [conversationId, setConversationId] = useState<
        string | undefined
    >();

    const [loading, setLoading] = useState(false);

    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {

        if (conversation) {

            setMessages(conversation.messages);

            setConversationId(conversation.id);

        } else {

            setMessages([]);

            setConversationId(undefined);

        }

    }, [conversation]);

    useEffect(() => {

        bottomRef.current?.scrollIntoView({
            behavior: "smooth",
        });

    }, [messages]);

    async function handleSend(text: string) {

        const userMessage: Message = {
            sender: "user",
            text,
        };

        setMessages(prev => [
            ...prev,
            userMessage,
        ]);

        setLoading(true);

        try {

            if (!business?.slug) throw new Error("Business context is unavailable");
            const response = await sendMessage(text, business.slug, conversationId);

            if (!conversationId) {

                setConversationId(
                    response.conversation_id
                );

                await refreshConversations();

            }

            const aiMessage: Message = {

                sender: "ai",

                text: response.reply,

            };

            setMessages(prev => [
                ...prev,
                aiMessage,
            ]);

        } catch (err) {

            console.error(err);

            setMessages(prev => [

                ...prev,

                {

                    sender: "ai",

                    text:
                        "Sorry, something went wrong.",

                },

            ]);

        } finally {

            setLoading(false);

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

                    AI Employee

                </p>

            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">

                {
                    messages.length === 0 && (

                        <div className="text-center text-gray-400 mt-16">

                            <h2 className="text-2xl font-semibold">

                                👋 Welcome

                            </h2>

                            <p className="mt-3">

                                Start chatting with your AI employee.

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

                {

                    loading && (

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
