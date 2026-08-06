import StatusIndicator from "./StatusIndicator";
import type { EmployeeInfo } from "../../types/ai";

export default function EmployeeStatusCard({ employee }: { employee: EmployeeInfo }) {
  return (
    <div className="bg-white rounded-xl border p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src={employee.avatar || "/avatar-placeholder.png"} alt={employee.name} className="w-12 h-12 rounded-full object-cover" />
          <div>
            <div className="text-sm font-semibold">{employee.name}</div>
            <div className="text-xs text-slate-500 flex items-center">
              <StatusIndicator status={employee.status} />
              <span>{employee.status}</span>
              <span className="mx-2">•</span>
              <span>{employee.online ? "Online" : "Offline"}</span>
            </div>
          </div>
        </div>

        <div className="text-right">
          <div className="text-sm font-medium">{employee.confidence ? `${Math.round(employee.confidence * 100)}%` : "—"}</div>
          <div className="text-xs text-slate-400">Confidence</div>
        </div>
      </div>

      <div className="mt-3 text-sm text-slate-600">
        <div><strong>Task:</strong> {employee.current_task || "No active task"}</div>
        <div className="mt-2"><strong>Memory:</strong> {employee.memory_usage ? `${employee.memory_usage}%` : "—"}</div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {employee.tools?.map((t) => (
          <span key={t} className="text-xs bg-slate-50 border rounded-full px-2 py-1 text-slate-700">{t}</span>
        ))}
      </div>
    </div>
  );
}