export default function AIHealthCard({ healthy, uptime, notes }: { healthy: boolean; uptime?: string; notes?: string }) {
  return (
    <div className="bg-white border rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold">{healthy ? "Healthy" : "Degraded"}</h4>
          <div className="text-xs text-slate-500">Model & tooling health</div>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs ${healthy ? "bg-emerald-50 text-emerald-700" : "bg-yellow-50 text-yellow-700"}`}>
          {healthy ? "OK" : "Issue"}
        </div>
      </div>
      {uptime && <div className="mt-3 text-xs text-slate-500">Uptime: {uptime}</div>}
      {notes && <div className="mt-2 text-xs text-slate-400">{notes}</div>}
    </div>
  );
}