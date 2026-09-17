import { useRef, useState, type FormEvent } from "react";
import { Bot, Send } from "lucide-react";

import Button from "../ui/Button";
import Input from "../ui/Input";
import { askAssistant } from "../../services/marketplace";
import { getErrorMessage } from "../../services/api";
import { getOrCreateVisitorId } from "../../utils/visitorId";

interface ChatTurn {
    role: "user" | "assistant";
    text: string;
}

/** The one real "Talk to AI Assistant" implementation - used both inside
 * PropertyDetail's quick-question modal and the dedicated /buyer/assistant
 * page, so there is exactly one chatbot integration in the buyer product,
 * not two. Posts to the same public customer-conversation pipeline the
 * website widget and marketplace already use (see conversation_service.py):
 * a real Groq/agency-configured LLM call grounded in structured database
 * facts, never a second, invented AI layer. `propertyId` is optional -
 * omitting it still grounds the reply in the agency's own knowledge base,
 * just without one specific listing's live price/availability. */
export default function AssistantChat({
    agencySlug,
    agencyName,
    propertyId,
    contextLabel,
    compact = false,
}: {
    agencySlug: string;
    agencyName: string;
    propertyId?: string;
    /** A short "you're asking about X" chip, e.g. "Skyline Residences —
     * Unit T2-0901" - so the buyer always knows what the assistant is
     * grounded in, per the product spec. */
    contextLabel?: string;
    /** Shorter chat window for the modal; taller for the full page. */
    compact?: boolean;
}) {
    const [turns, setTurns] = useState<ChatTurn[]>([]);
    const [input, setInput] = useState("");
    const [sending, setSending] = useState(false);
    const [error, setError] = useState("");
    const conversationIdRef = useRef<string | null>(null);
    const visitorIdRef = useRef(getOrCreateVisitorId());

    async function handleSend(e: FormEvent) {
        e.preventDefault();
        const message = input.trim();
        if (!message || sending) return;

        setTurns((t) => [...t, { role: "user", text: message }]);
        setInput("");
        setSending(true);
        setError("");
        try {
            const result = await askAssistant({
                agencySlug,
                visitorId: visitorIdRef.current,
                conversationId: conversationIdRef.current,
                message,
                propertyId,
            });
            conversationIdRef.current = result.conversation_id;
            setTurns((t) => [...t, { role: "assistant", text: result.reply }]);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSending(false);
        }
    }

    return (
        <div className={`flex flex-col ${compact ? "h-[26rem]" : "h-[32rem]"}`}>
            {contextLabel && (
                <div className="mb-3 inline-flex self-start items-center gap-1.5 text-xs font-medium text-brand-700 bg-brand-50 rounded-full px-3 py-1.5">
                    <Bot size={12} aria-hidden="true" />
                    You're asking about {contextLabel}
                </div>
            )}

            <div className="flex-1 overflow-y-auto space-y-3 pr-1 thin-scrollbar">
                {turns.length === 0 && (
                    <div className="flex items-start gap-3 text-sm text-slate-500">
                        <div className="w-8 h-8 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center shrink-0">
                            <Bot size={16} aria-hidden="true" />
                        </div>
                        <p>
                            Ask about price, availability, amenities, similar units, or request a site
                            visit - answers are grounded in {agencyName}'s real listing data, never guessed.
                        </p>
                    </div>
                )}
                {turns.map((turn, i) => (
                    <div key={i} className={`flex ${turn.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div
                            className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                                turn.role === "user" ? "bg-ink-950 text-white" : "bg-stone-100 text-ink-950"
                            }`}
                        >
                            {turn.text}
                        </div>
                    </div>
                ))}
                {sending && (
                    <div className="flex justify-start">
                        <div className="bg-stone-100 text-slate-400 rounded-2xl px-4 py-2.5 text-sm">Thinking…</div>
                    </div>
                )}
            </div>

            {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

            <form onSubmit={handleSend} className="flex items-center gap-2 pt-3 border-t border-slate-100 mt-3">
                <Input
                    autoFocus
                    placeholder="Ask a question…"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={sending}
                />
                <Button type="submit" size="sm" loading={sending} disabled={!input.trim()}>
                    <Send size={15} />
                </Button>
            </form>
        </div>
    );
}
