import { Link } from "react-router-dom";
import type { EmployeeInfo } from "../../types/ai";
import StatusIndicator from "./StatusIndicator";

export default function EmployeeCard({ employee }: { employee: EmployeeInfo }) {
  return (
    <Link to={`/employee?emp=${encodeURIComponent(employee.id)}`} className="block">
      <div className="bg-white rounded-xl border p-4 shadow-sm hover:shadow-md transition">
        <div className="flex items-start gap-4">
          <img src={employee.avatar || "/avatar-placeholder.png"} alt={employee.name} className="w-12 h-12 rounded-full object-cover" />
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold">{employee.name}</div>
              <div className="flex items-center">
                <StatusIndicator status={employee.status} />
                <div className="text-xs text-slate-500">{employee.status}</div>
              </div>
            </div>

            <div className="text-sm text-slate-500 mt-2">{employee.current_task || employee.last_response || "Idle"}</div>

            <div className="mt-3 flex items-center justify-between">
              <div className="flex gap-2">
                {employee.tools.slice(0, 3).map((t) => (
                  <span key={t} className="text-xs bg-slate-50 border rounded-full px-2 py-1 text-slate-700">{t}</span>
                ))}
              </div>
              <div className="text-xs text-slate-400">{employee.memory_usage ? `${employee.memory_usage}% mem` : ""}</div>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}