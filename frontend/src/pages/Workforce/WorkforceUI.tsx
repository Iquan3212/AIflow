import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import EmployeeStatusCard from "../../components/ai/EmployeeStatusCard";
import { useWorkforce } from "../../hooks/useWorkforce";
import { Sparkles } from "lucide-react";

export default function WorkforceUI() {
  const { employees, loading, error, reload } = useWorkforce();

  return (
    <AppShell>
      <PageHeader
        title="AI Workforce"
        description="The specialists your Manager AI can delegate to."
      />

      {loading && <LoadingState label="Loading workforce…" />}
      {!loading && error && <ErrorState message={error} onRetry={reload} />}
      {!loading && !error && employees && employees.length === 0 && (
        <EmptyState icon={<Sparkles size={32} />} title="No employees registered" />
      )}
      {!loading && !error && employees && employees.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {employees.map((employee) => (
            <EmployeeStatusCard key={employee.id} employee={employee} />
          ))}
        </div>
      )}
    </AppShell>
  );
}
