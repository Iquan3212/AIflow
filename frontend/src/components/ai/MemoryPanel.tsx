export default function MemoryPanel({ summary, facts, profile }: { summary?: string; facts?: string[]; profile?: Record<string, unknown> }) {
  return (
    <div className="bg-white border rounded-xl p-4 shadow-sm">
      <h3 className="text-sm font-semibold mb-2">Memory</h3>
      <div className="text-xs text-slate-600 mb-3 whitespace-pre-wrap">{summary || "No summary available."}</div>
      <div className="text-xs text-slate-500">
        <div><strong>Facts:</strong></div>
        <ul className="list-disc ml-5 mt-1">
          {(facts && facts.length) ? facts.map((f) => <li key={f} className="truncate">{f}</li>) : <li className="text-slate-400">None</li>}
        </ul>
      </div>
      {profile && Object.keys(profile).length > 0 && (
        <div className="mt-3 text-xs text-slate-500">
          <div><strong>Profile</strong></div>
          <pre className="text-xs mt-1 text-slate-600">{JSON.stringify(profile, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
