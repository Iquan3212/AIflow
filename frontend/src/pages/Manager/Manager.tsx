import { useEffect, useRef, useState } from "react";
import Layout from "../../components/dashboard/Layout";
import { useManagerChat } from "../../hooks/useManagerChat";
import { getConversation as getConv } from "../../services/manager";
import type { ConversationMessage } from "../../types/ai";
import AgentBadge from "../../components/ai/AgentBadge";
import DelegationBadge from "../../components/ai/DelegationBadge";
import ToolBadge from "../../components/ai/ToolBadge";

export default function Manager() {
  const { send, loading, typing } = useManagerChat();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [text, setText] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const data = await getConv(undefined);
        setConversationId(data.conversation_id);
        // normalize messages if provided; fall back to empty
        setMessages(data.messages ?? []);
      } catch (err) {
        // ignore
      }
    })();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  async function handleSend() {
    const content = text.trim();
    if (!content) return;
    // append user message optimistically
    const userMsg: ConversationMessage = { role: "user", content, timestamp: new Date().toISOString() };
    setMessages((m) => [...m, userMsg]);
    setText("");
    const resp = await send(content, conversationId);
    setConversationId(resp.conversation_id);
    // manager reply is resp.reply; manager_result may contain per-employee replies
    const assistantMsg: ConversationMessage = {
      role: "assistant",
      content: resp.reply,
      agent: "manager",
      timestamp: new Date().toISOString(),
    };
    setMessages((m) => [...m, assistantMsg]);
    // attach employee-specific replies as separate messages
    if (resp.manager_result?.employee_results) {
      const entries = Object.entries(resp.manager_result.employee_results);
      for (const [emp, res] of entries) {
        const emsg: ConversationMessage = {
          role: "assistant",
          content: res.reply ?? "",
          agent: emp,
          timestamp: new Date().toISOString(),
          tool: res.tool_result ? { name: "tool", status: "success", result: res.tool_result } : undefined,
        };
        setMessages((m) => [...m, emsg]);
      }
    }
  }

  return (
    <Layout>
      <div className="max-w-5xl mx-auto h-full flex flex-col">
        <div className="mb-6">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-blue-600 text-white p-3">M</div>
            <div>
              <h1 className="text-3xl font-bold">Manager AI</h1>
              <p className="text-slate-500">Unified coordinator for the AI Workforce</p>
            </div>
          </div>
        </div>

        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 flex-1 min-h-[560px] flex flex-col">
          <div className="px-6 py-4 border-b flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Manager</h2>
              <p className="text-sm text-slate-500">Delegation, synthesis, and coordination</p>
            </div>
            <span className="text-sm font-medium text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full">Online</span>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50">
            {messages.map((item, index) => (
              <div key={`${item.role}-${index}-${item.timestamp}`} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[78%] rounded-2xl px-4 py-3 whitespace-pre-wrap ${item.role === "user" ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-800"}`}>
                  <div className="flex items-center gap-2 mb-2">
                    {item.agent && <AgentBadge agent={item.agent} />}
                    {item.delegation && <DelegationBadge from={item.delegation.from} to={item.delegation.to} />}
                    {item.tool && <ToolBadge tool={item.tool.name} />}
                    <div className="text-xs text-slate-400 ml-auto">{item.timestamp ? new Date(item.timestamp).toLocaleString() : ""}</div>
                  </div>
                  <div>{item.content}</div>
                </div>
              </div>
            ))}
            {typing && <div className="text-sm text-slate-500">Manager is thinking…</div>}
            <div ref={bottomRef} />
          </div>

          <div className="p-4 border-t flex gap-3">
            <textarea
              rows={2}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              placeholder="Ask the Manager AI…"
              className="flex-1 border rounded-xl px-4 py-3 resize-none outline-none focus:border-blue-500"
              disabled={loading}
            />
            <button onClick={() => void handleSend()} disabled={loading || !text.trim()} className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-5 disabled:opacity-50">
              Send
            </button>
          </div>
        </section>
      </div>
    </Layout>
  );
}