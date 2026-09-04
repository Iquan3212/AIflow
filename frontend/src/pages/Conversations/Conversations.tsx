import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import { ErrorState, LoadingState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";

import ConversationList from "../../components/conversations/ConversationList";
import ChatWindow from "../../components/conversations/ChatWindow";
import CustomerInfo from "../../components/conversations/CustomerInfo";

import { getConversations } from "../../services/conversation";

import type { Conversation } from "../../types/conversation";

export default function Conversations() {
    const [conversations, setConversations] = useState<Conversation[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);

    // Derived, not stored: the list (fetched fresh) is the single source of
    // truth, and every panel (list, chat, customer details) reads the same
    // object for the selected conversation - that's the fix for Customer
    // Details and the chat panel disagreeing about message count/identity.
    const selectedConversation = conversations?.find((c) => c.id === selectedId) ?? null;

    async function loadConversations() {
        setError(null);
        try {
            const data = await getConversations();
            setConversations(data);
            setSelectedId((current) => current ?? data[0]?.id ?? null);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    async function handleMessageSent(conversationId: string) {
        setError(null);
        try {
            const data = await getConversations();
            setConversations(data);
            setSelectedId(conversationId);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        // The initial fetch deliberately runs once; later refreshes are
        // triggered by the active chat window after a message round-trip.
        void loadConversations();
    }, []);

    return (
        <AppShell>
            <PageHeader title="Conversations" description="Every customer chat handled by your AI Workforce." />

            {conversations === null && !error && <LoadingState label="Loading conversations…" />}
            {error && <ErrorState message={error} onRetry={loadConversations} />}

            {conversations !== null && !error && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 h-[calc(100vh-13rem)]">
                    <div className={`lg:col-span-3 min-h-0 ${selectedConversation ? "hidden lg:block" : ""}`}>
                        <ConversationList
                            conversations={conversations}
                            selected={selectedConversation}
                            onSelect={(c) => setSelectedId(c.id)}
                        />
                    </div>

                    <div className={`lg:col-span-6 min-h-0 flex flex-col ${selectedConversation ? "" : "hidden lg:block"}`}>
                        {selectedConversation && (
                            <button
                                onClick={() => setSelectedId(null)}
                                className="lg:hidden flex items-center gap-1 text-sm text-slate-600 mb-2"
                            >
                                <ArrowLeft size={16} />
                                All conversations
                            </button>
                        )}
                        <div className="flex-1 min-h-0">
                            <ChatWindow conversation={selectedConversation} onMessageSent={handleMessageSent} />
                        </div>
                    </div>

                    <div className="hidden lg:block lg:col-span-3 min-h-0">
                        <CustomerInfo conversation={selectedConversation} />
                    </div>
                </div>
            )}
        </AppShell>
    );
}
