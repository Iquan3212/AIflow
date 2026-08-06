export default function AgentBadge({ agent }: { agent: string }) {
  return (
    <span className="inline-flex items-center text-xs bg-slate-100 border border-slate-200 rounded-full px-2 py-1 text-slate-700">
      {agent}
    </span>
  );
}