export default function DelegationBadge({ from, to }: { from: string; to: string }) {
  return (
    <div className="inline-flex items-center gap-2 bg-slate-50 border border-slate-100 rounded-lg px-3 py-1 text-sm text-slate-700">
      <strong className="text-slate-800">{from}</strong>
      <span className="opacity-60">→</span>
      <strong className="text-emerald-700">{to}</strong>
    </div>
  );
}