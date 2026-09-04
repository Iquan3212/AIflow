import StatusIndicator from "./StatusIndicator";
import type { EmployeeInfo } from "../../types/ai";

export default function EmployeeStatusCard({ employee }: { employee: EmployeeInfo }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
      <div className="flex items-center gap-3">
        {employee.avatar ? (
          <img src={employee.avatar} alt="" className="w-12 h-12 rounded-full object-cover" />
        ) : (
          <div className="w-12 h-12 rounded-full bg-indigo-600 text-white flex items-center justify-center font-semibold">
            {employee.name.charAt(0).toUpperCase()}
          </div>
        )}
        <div>
          <div className="text-sm font-semibold text-slate-900">{employee.name}</div>
          <div className="text-xs text-slate-500 flex items-center gap-1.5">
            <StatusIndicator status={employee.status} />
            <span className="capitalize">{employee.status}</span>
          </div>
        </div>
      </div>

      {employee.current_task && (
        <p className="mt-3 text-sm text-slate-600">{employee.current_task}</p>
      )}

      {employee.confidence != null && (
        <p className="mt-2 text-xs text-slate-400">
          Confidence: <span className="text-slate-600 font-medium">{Math.round(employee.confidence * 100)}%</span>
        </p>
      )}

      {employee.tools && employee.tools.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {employee.tools.map((t) => (
            <span key={t} className="text-xs bg-slate-100 rounded-full px-2 py-0.5 text-slate-600">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
