import type { EmployeeStatus } from "../../types/ai";

const dotColor = (status: EmployeeStatus) => {
  switch (status) {
    case "online":
    case "working":
    case "thinking":
      return "bg-emerald-500";
    case "busy":
      return "bg-yellow-500";
    case "idle":
      return "bg-sky-400";
    case "offline":
    default:
      return "bg-slate-400";
  }
};

export default function StatusIndicator({ status }: { status: EmployeeStatus }) {
  return <span className={`inline-block w-3 h-3 rounded-full ${dotColor(status)} mr-2`} />;
}