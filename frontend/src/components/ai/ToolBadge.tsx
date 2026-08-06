export default function ToolBadge({ tool }: { tool: string }) {
  return (
    <span className="inline-flex items-center text-xs bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-full px-2 py-1">
      {tool}
    </span>
  );
}