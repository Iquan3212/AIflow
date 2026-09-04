import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import { ErrorState } from "../../components/ui/States";
import { useManagerChat } from "../../hooks/useManagerChat";
import { getConversation as getConv } from "../../services/manager";
import { getErrorMessage } from "../../services/api";
import type { ConversationMessage } from "../../types/ai";
import AgentBadge from "../../components/ai/AgentBadge";
import DelegationBadge from "../../components/ai/DelegationBadge";
import ToolBadge from "../../components/ai/ToolBadge";
import MemoryPanel from "../../components/ai/MemoryPanel";
import TaskTimeline from "../../components/ai/TaskTimeline";

export default function Manager() {
  const { send, loading, typing } = useManagerChat();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [text, setText] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [memory, setMemory] = useState<{ summary?: string | null; facts?: string[] } | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  async function loadConversation() {
    setLoadError(null);
    try {
      const data = await getConv(undefined);
      setConversationId(data.conversation_id);
      setMessages(data.messages ?? []);
    } catch (err) {
      setLoadError(getErrorMessage(err));
    }
  }

  useEffect(() => {
    void loadConversation();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  async function handleSend() {
    const content = text.trim();
    if (!content) return;
    const userMsg: ConversationMessage = { role: "user", content, timestamp: new Date().toISOString() };
    setMessages((m) => [...m, userMsg]);
    setText("");

    try {
      const resp = await send(content, conversationId);
      setConversationId(resp.conversation_id);
      setMemory(resp.manager_result?.memory ?? null);

      const assistantMsg: ConversationMessage = {
        role: "assistant",
        content: resp.reply,
        agent: "manager",
        timestamp: new Date().toISOString(),
      };
      setMessages((m) => [...m, assistantMsg]);

      if (resp.manager_result?.employee_results) {
        for (const [emp, res] of Object.entries(resp.manager_result.employee_results)) {
          if (!res.reply) continue;
          const emsg: ConversationMessage = {
            role: "assistant",
            content: res.reply,
            agent: emp,
            timestamp: new Date().toISOString(),
            tool: res.tool_result ? { name: "tool", status: "success", result: res.tool_result } : undefined,
          };
          setMessages((m) => [...m, emsg]);
        }
      }
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: getErrorMessage(err), agent: "manager", timestamp: new Date().toISOString() },
      ]);
    }
  }

  const timelineItems = messages
    .filter((m) => m.role === "assistant" && m.timestamp)
    .map((m) => ({
      time: m.timestamp as string,
      text: `${m.agent ? m.agent.charAt(0).toUpperCase() + m.agent.slice(1) : "Manager"} responded`,
    }))
    .slice(-8);

  return (
    <AppShell>
      <PageHeader title="Manager AI" description="Delegates your request to the right specialist and synthesizes one answer." />

      {loadError && <ErrorState message={loadError} onRetry={loadConversation} />}

      {!loadError && (
        <div className="flex flex-col lg:flex-row gap-4 h-[calc(100vh-13rem)]">
          <Card className="flex-1 flex flex-col min-h-0">
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700">Conversation</span>
              <Badge tone="success">Online</Badge>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-slate-50">
              {messages.map((item, index) => (
                <div key={`${item.role}-${index}-${item.timestamp}`} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] rounded-xl px-4 py-3 whitespace-pre-wrap text-sm ${item.role === "user" ? "bg-indigo-600 text-white" : "bg-white border border-slate-200 text-slate-800"}`}>
                    {(item.agent || item.delegation || item.tool) && (
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        {item.agent && <AgentBadge agent={item.agent} />}
                        {item.delegation && <DelegationBadge from={item.delegation.from} to={item.delegation.to} />}
                        {item.tool && <ToolBadge tool={item.tool.name} />}
                      </div>
                    )}
                    <div>{item.content}</div>
                    {item.timestamp && (
                      <div className={`text-xs mt-1.5 ${item.role === "user" ? "text-indigo-200" : "text-slate-400"}`}>
                        {new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {typing && <div className="text-sm text-slate-500">Manager is thinking…</div>}
              <div ref={bottomRef} />
            </div>

            <div className="p-4 border-t border-slate-200 flex gap-3">
              <label htmlFor="manager-input" className="sr-only">Message the Manager AI</label>
              <textarea
                id="manager-input"
                rows={1}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void handleSend();
                  }
                }}
                placeholder="Ask the Manager AI…"
                className="flex-1 border border-slate-300 rounded-lg px-4 py-2.5 resize-none outline-none focus:border-indigo-500 text-sm"
                disabled={loading}
              />
              <button
                onClick={() => void handleSend()}
                disabled={loading || !text.trim()}
                aria-label="Send message"
                className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white rounded-lg px-4 flex items-center justify-center"
              >
                <Send size={18} />
              </button>
            </div>
          </Card>

          <div className="lg:w-72 shrink-0 space-y-4 overflow-y-auto">
            <MemoryPanel summary={memory?.summary ?? undefined} facts={memory?.facts} />
            <TaskTimeline items={timelineItems} />
          </div>
        </div>
      )}
    </AppShell>
  );
}
