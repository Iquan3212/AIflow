import { useEffect, useState } from "react";

import Layout from "../../components/dashboard/Layout";

import ConversationList from "../../components/conversations/ConversationList";
import ChatWindow from "../../components/conversations/ChatWindow";
import CustomerInfo from "../../components/conversations/CustomerInfo";

import { getConversations } from "../../services/conversation";

import type {
    Conversation,
} from "../../types/conversation";

export default function Conversations() {

    const [
        conversations,
        setConversations,
    ] = useState<Conversation[]>([]);

    const [
        selectedConversation,
        setSelectedConversation,
    ] = useState<Conversation | null>(null);

    async function loadConversations() {

        try {

            const data =
                await getConversations();

            setConversations(data);

            if (

                data.length > 0 &&

                !selectedConversation

            ) {

                setSelectedConversation(
                    data[0]
                );

            }

        } catch (err) {

            console.error(err);

        }

    }

    useEffect(() => {

        // The initial fetch deliberately runs once; later refreshes are
        // triggered by the active chat window after a new conversation.
        loadConversations();

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (

        <Layout>

            <div className="grid grid-cols-12 gap-6 h-[calc(100vh-150px)]">

                <div className="col-span-3">

                    <ConversationList

                        conversations={conversations}

                        selected={selectedConversation}

                        onSelect={
                            setSelectedConversation
                        }

                    />

                </div>

                <div className="col-span-6">

                    <ChatWindow

                        conversation={
                            selectedConversation
                        }

                        refreshConversations={
                            loadConversations
                        }

                    />

                </div>

                <div className="col-span-3">

                    <CustomerInfo

                        conversation={
                            selectedConversation
                        }

                    />

                </div>

            </div>

        </Layout>

    );

}
