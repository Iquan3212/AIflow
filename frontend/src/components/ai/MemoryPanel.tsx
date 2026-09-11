import { Brain } from "lucide-react";
import Card from "../ui/Card";

export default function MemoryPanel({ summary, facts, profile }: { summary?: string; facts?: string[]; profile?: Record<string, unknown> }) {
  return (
    <Card className="p-5">
      <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-3">
        <Brain size={15} className="text-brand-500" aria-hidden="true" /> Memory
      </h3>
      <p className="text-xs text-slate-500 leading-relaxed whitespace-pre-wrap">{summary || "No summary yet — it builds as the conversation continues."}</p>
      {facts && facts.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {facts.map((f) => (
            <li key={f} className="text-xs text-slate-600 bg-stone-100 rounded-lg px-2.5 py-1.5 truncate">{f}</li>
          ))}
        </ul>
      )}
      {profile && Object.keys(profile).length > 0 && (
        <pre className="mt-3 text-[11px] font-mono-data text-slate-500 bg-stone-100 rounded-lg p-2.5 overflow-x-auto">
          {JSON.stringify(profile, null, 2)}
        </pre>
      )}
    </Card>
  );
}
