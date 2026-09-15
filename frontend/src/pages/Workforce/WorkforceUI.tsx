import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Sparkles, XCircle } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import EmployeeStatusCard from "../../components/ai/EmployeeStatusCard";
import { useWorkforce } from "../../hooks/useWorkforce";
import { decideAIApproval, listAIApprovals } from "../../services/workforce";
import { getErrorMessage } from "../../services/api";
import type { AIActionApprovalOut } from "../../types/ai";

/** Minimal AI-action approval inbox (Phase 10C) - same list/approve/
 * reject pattern already used for workflow approvals
 * (Workflows.tsx/decideWorkflowApproval), just pointed at the generic
 * AIActionApproval primitive instead. Deliberately not a full execution-
 * monitoring dashboard - just enough to review and decide. */
function PendingAIActions() {
    const [approvals, setApprovals] = useState<AIActionApprovalOut[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busyIds, setBusyIds] = useState<Set<string>>(new Set());

    const load = useCallback(async () => {
        try {
            setApprovals(await listAIApprovals());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    async function handleDecide(approval: AIActionApprovalOut, approve: boolean) {
        setBusyIds((current) => new Set(current).add(approval.id));
        try {
            await decideAIApproval(approval.id, approve);
            setApprovals((current) => current?.filter((a) => a.id !== approval.id) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setBusyIds((current) => {
                const next = new Set(current);
                next.delete(approval.id);
                return next;
            });
        }
    }

    if (error) return <ErrorState message={error} onRetry={load} />;
    if (!approvals || approvals.length === 0) return null;

    return (
        <Card className="p-4 mb-8 border-amber-200 bg-amber-50">
            <h2 className="text-sm font-semibold text-amber-900 mb-3">
                {approvals.length} AI action{approvals.length === 1 ? "" : "s"} awaiting your approval
            </h2>
            <ul className="space-y-2">
                {approvals.map((approval) => (
                    <li key={approval.id} className="flex items-center justify-between gap-3 bg-white rounded-lg border border-amber-200 px-3 py-2">
                        <div className="min-w-0">
                            <p className="text-sm text-slate-800 truncate">{approval.summary}</p>
                            <p className="text-xs text-slate-400">
                                {approval.requested_by_employee} · {new Date(approval.created_at).toLocaleString()}
                            </p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                            <Button size="sm" onClick={() => handleDecide(approval, true)} loading={busyIds.has(approval.id)}>
                                <CheckCircle2 size={14} aria-hidden="true" />
                                Approve
                            </Button>
                            <Button size="sm" variant="secondary" onClick={() => handleDecide(approval, false)} disabled={busyIds.has(approval.id)}>
                                <XCircle size={14} aria-hidden="true" />
                                Reject
                            </Button>
                        </div>
                    </li>
                ))}
            </ul>
        </Card>
    );
}

export default function WorkforceUI() {
  const { employees, loading, error, reload } = useWorkforce();

  const manager = employees?.find((e) => e.id === "manager");
  const specialists = employees?.filter((e) => e.id !== "manager") ?? [];

  return (
    <AppShell>
      <PageHeader
        eyebrow="AI Workforce"
        title="Your coordinated AI Workforce"
        description="Manager AI reads every conversation and delegates to the specialist best equipped to handle it. Lead Qualification, Property Matching, Real Estate Sales, Site Visit, and Customer Relations are the real-estate-specialized personas — the rest of the roster is still general-purpose."
      />

      <PendingAIActions />

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
