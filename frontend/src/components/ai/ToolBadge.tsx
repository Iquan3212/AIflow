export default function ToolBadge({ tool }: { tool: string }) {
  return (
    <span className="inline-flex items-center text-xs bg-brand-50 text-brand-700 border border-brand-100 rounded-full px-2 py-1">
      {tool}
    </span>
  );
}