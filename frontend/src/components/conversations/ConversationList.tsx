import type { Conversation } from "../../types/conversation";
import Badge from "../ui/Badge";
import type { BadgeTone } from "../ui/Badge";

type Props = {
    conversations: Conversation[];
    selected: Conversation | null;
    onSelect: (conversation: Conversation) => void;
};

const CHANNEL_LABELS: Record<string, string> = {
    website: "Website",
    whatsapp: "WhatsApp",
    instagram: "Instagram",
};

const CHANNEL_TONES: Record<string, BadgeTone> = {
    website: "neutral",
    whatsapp: "success",
    instagram: "info",
};

export function ChannelBadge({ channel }: { channel: string }) {
    return (
        <Badge tone={CHANNEL_TONES[channel] ?? "neutral"}>
            {CHANNEL_LABELS[channel] ?? channel}
        </Badge>
    );
}

export default function ConversationList({
    conversations,
    selected,
    onSelect,
}: Props) {

    return (

        <div className="bg-white rounded-2xl shadow h-full flex flex-col">

            <div className="p-5 border-b">

                <h2 className="text-xl font-bold">
                    Conversations
                </h2>

                <p className="text-gray-500 text-sm mt-1">
                    {conversations.length} conversation(s)
                </p>

            </div>

            <div className="flex-1 overflow-y-auto">

                {conversations.length === 0 ? (

                    <div className="p-6 text-center text-gray-400">

                        No conversations yet.

                    </div>

                ) : (

                    conversations.map((conversation) => (

                        <button
                            key={conversation.id}
                            type="button"
                            onClick={() => onSelect(conversation)}
                            aria-current={selected?.id === conversation.id}
                            className={`w-full text-left cursor-pointer border-b transition p-5

                            ${
                                selected?.id === conversation.id
                                    ? "bg-blue-50"
                                    : "hover:bg-gray-50"
                            }`}
                        >

                            <div className="flex items-center justify-between gap-2">
                                <div className="font-semibold">
                                    {conversation.name}
                                </div>
                                <ChannelBadge channel={conversation.channel} />
                            </div>

                            <div className="text-sm text-gray-500">

                                {conversation.phone || "No phone"}

                            </div>

                            <div className="text-xs text-gray-400 mt-2">

                                {
                                    conversation.total_messages
                                }

                                {" "}messages

                            </div>

                        </button>

                    ))

                )}

            </div>

        </div>

    );

}