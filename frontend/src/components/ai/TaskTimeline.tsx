import { History } from "lucide-react";
import Card from "../ui/Card";

export default function TaskTimeline({ items }: { items: { time: string; text: string }[] }) {
  return (
    <Card className="p-5">
      <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-4">
        <History size={15} className="text-brand-500" aria-hidden="true" /> Recent activity
      </h3>
      {items.length === 0 ? (
        <p className="text-xs text-slate-400">Nothing yet this session.</p>
      ) : (
        <ol className="relative space-y-4 before:absolute before:left-[3px] before:top-1.5 before:bottom-1.5 before:w-px before:bg-slate-200">
          {items.map((it, idx) => (
            <li key={idx} className="relative pl-5">
              <span className="absolute left-0 top-1.5 w-[7px] h-[7px] rounded-full bg-brand-500" aria-hidden="true" />
              <p className="text-xs text-slate-600">{it.text}</p>
              <p className="text-[11px] text-slate-400 mt-0.5">{new Date(it.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
