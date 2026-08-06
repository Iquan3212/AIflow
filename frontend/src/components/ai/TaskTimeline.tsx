export default function TaskTimeline({ items }: { items: { time: string; text: string }[] }) {
  return (
    <div className="bg-white border rounded-xl p-4 shadow-sm">
      <h3 className="text-sm font-semibold mb-3">Task Timeline</h3>
      <ol className="space-y-3 text-xs">
        {items.map((it, idx) => (
          <li key={idx} className="flex items-start gap-3">
            <div className="w-20 text-slate-400">{new Date(it.time).toLocaleString()}</div>
            <div className="flex-1 text-slate-600">{it.text}</div>
          </li>
        ))}
      </ol>
    </div>
  );
}