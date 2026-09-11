import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import EmployeeStatusCard from "../../components/ai/EmployeeStatusCard";
import { useWorkforce } from "../../hooks/useWorkforce";
import { Sparkles } from "lucide-react";

export default function WorkforceUI() {
  const { employees, loading, error, reload } = useWorkforce();

  const manager = employees?.find((e) => e.id === "manager");
  const specialists = employees?.filter((e) => e.id !== "manager") ?? [];

  return (
    <AppShell>
      <PageHeader
        eyebrow="AI Workforce"
        title="Your coordinated AI Workforce"
        description="Manager AI reads every conversation and delegates to the specialist best equipped to handle it. Roles are general-purpose today — real-estate-specialized personas aren't built yet."
      />

      {loading && <LoadingState label="Loading workforce…" />}
      {!loading && error && <ErrorState message={error} onRetry={reload} />}
      {!loading && !error && employees && employees.length === 0 && (
        <EmptyState icon={<Sparkles size={28} />} title="No employees registered" />
      )}

      {!loading && !error && employees && employees.length > 0 && (
        <div className="space-y-8">
          {manager && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">Coordinator</p>
              <div className="max-w-sm">
                <EmployeeStatusCard employee={manager} highlight />
              </div>
            </div>
          )}

          {specialists.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">Specialists</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {specialists.map((employee) => (
                  <EmployeeStatusCard key={employee.id} employee={employee} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
