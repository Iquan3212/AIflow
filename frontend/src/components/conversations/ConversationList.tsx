import { MessageSquare } from "lucide-react";

import type { Conversation } from "../../types/conversation";
import Badge from "../ui/Badge";
import type { BadgeTone } from "../ui/Badge";
import { EmptyState } from "../ui/States";

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
    return <Badge tone={CHANNEL_TONES[channel] ?? "neutral"}>{CHANNEL_LABELS[channel] ?? channel}</Badge>;
}

export default function ConversationList({ conversations, selected, onSelect }: Props) {
    return (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-soft h-full flex flex-col">
            <div className="px-5 py-4 border-b border-slate-100">
                <h2 className="font-display text-lg font-semibold text-slate-900">Conversations</h2>
                <p className="text-slate-500 text-sm mt-0.5">{conversations.length} conversation(s)</p>
            </div>

            <div className="flex-1 overflow-y-auto thin-scrollbar">
                {conversations.length === 0 ? (
                    <EmptyState icon={<MessageSquare size={26} />} title="No conversations yet" />
                ) : (
                    conversations.map((conversation) => {
                        const isSelected = selected?.id === conversation.id;
                        return (
                            <button
                                key={conversation.id}
                                type="button"
                                onClick={() => onSelect(conversation)}
                                aria-current={isSelected}
                                className={`w-full text-left border-b border-slate-100 transition-colors px-5 py-4 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-500 ${
                                    isSelected ? "bg-brand-50" : "hover:bg-slate-50"
                                }`}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <div className="font-semibold text-sm text-slate-900 truncate">{conversation.name}</div>
                                    <ChannelBadge channel={conversation.channel} />
                                </div>

                                <div className="text-sm text-slate-500 mt-0.5">{conversation.phone || "No phone"}</div>

                                <div className="text-xs text-slate-400 mt-2">{conversation.total_messages} messages</div>
                            </button>
                        );
                    })
                )}
            </div>
        </div>
    );
}
