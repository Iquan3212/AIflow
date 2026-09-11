import { useCallback, useEffect, useState } from "react";
import {
    CheckCircle2,
    ChevronDown,
    ChevronUp,
    Loader2,
    Play,
    Plus,
    Trash2,
    Workflow as WorkflowIcon,
    XCircle,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge, { type BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import {
    createWorkflow,
    decideWorkflowApproval,
    deleteWorkflow,
    disableWorkflow,
    enableWorkflow,
    listWorkflowApprovals,
    listWorkflowRuns,
    listWorkflows,
} from "../../services/workflows";
import {
    ACTION_LABELS,
    TRIGGER_LABELS,
    type ApprovalRequestOut,
    type Workflow,
    type WorkflowAction,
    type WorkflowCondition,
    type WorkflowRun,
    type WorkflowRunStatus,
    type WorkflowStatus,
    type WorkflowTriggerType,
} from "../../types/workflow";

const STATUS_TONE: Record<WorkflowStatus, BadgeTone> = {
    active: "success",
    paused: "warning",
    disabled: "neutral",
};

const RUN_STATUS_TONE: Record<WorkflowRunStatus, BadgeTone> = {
    pending: "neutral",
    running: "info",
    waiting_approval: "warning",
    succeeded: "success",
    failed: "danger",
    cancelled: "neutral",
};

// Mirrors backend/app/services/workflows/config.py's TRIGGER_FIELDS -
// the condition-field vocabulary is validated server-side regardless;
// this only limits what the form offers, for a non-technical owner.
const TRIGGER_FIELDS: Record<WorkflowTriggerType, string[]> = {
    lead_created: ["lead.status", "lead.service_interested", "lead.name", "lead.phone", "lead.email", "lead.budget"],
    appointment_created: ["appointment.status", "appointment.service", "appointment.customer_name", "appointment.source"],
    appointment_rescheduled: ["appointment.status", "appointment.service", "appointment.customer_name", "appointment.source"],
    appointment_cancelled: ["appointment.status", "appointment.service", "appointment.customer_name", "appointment.source"],
    support_escalated: ["support.priority", "support.status", "support.issue_summary"],
};

const TEMPLATES: Array<{
    label: string;
    description: string;
    trigger_type: WorkflowTriggerType;
    conditions: WorkflowCondition[];
    actions: WorkflowAction[];
}> = [
    {
        label: "New lead → draft a follow-up email (approval required)",
        description: "When a new lead specifies a service they're interested in, draft (and, once approved, send) a follow-up email.",
        trigger_type: "lead_created",
        conditions: [{ field: "lead.service_interested", op: "is_set" }],
        actions: [
            {
                type: "send_gmail",
                config: {
                    to_field: "lead.email",
                    subject: "Thanks for your interest, {lead_name}!",
                    body_template: "Hi {lead_name},\n\nThanks for reaching out about {lead_service_interested}. We'll be in touch shortly.\n\nBest,\nThe team",
                },
            },
        ],
    },
    {
        label: "Appointment confirmed → notify customer",
        description: "When an appointment is booked, send a confirmation notification (respects existing notification preferences).",
        trigger_type: "appointment_created",
        conditions: [{ field: "appointment.status", op: "eq", value: "scheduled" }],
        actions: [
            {
                type: "send_notification",
                config: {
                    event_type: "appointment_confirmed",
                    audience: "customer",
                    name_field: "appointment.customer_name",
                    email_field: "appointment.customer_email",
                    phone_field: "appointment.customer_phone",
                    subject: "Your appointment is confirmed",
                    body_template: "Hi {appointment_customer_name}, your appointment for {appointment_service} is confirmed.",
                },
            },
        ],
    },
    {
        label: "High-priority support → notify owner",
        description: "When a support ticket is escalated as high priority, notify the agency owner immediately.",
        trigger_type: "support_escalated",
        conditions: [{ field: "support.priority", op: "eq", value: "high" }],
        actions: [
            {
                type: "send_notification",
                config: {
                    event_type: "support_escalation",
                    audience: "owner",
                    subject: "Support escalation",
                    body_template: "A high-priority support issue was reported: {support_issue_summary}",
                },
            },
        ],
    },
];

function emptyAction(): WorkflowAction {
    return { type: "send_notification", config: { event_type: "new_lead", audience: "owner", subject: "", body_template: "" } };
}

export default function Workflows() {
    const [workflows, setWorkflows] = useState<Workflow[] | null>(null);
    const [approvals, setApprovals] = useState<ApprovalRequestOut[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
    const [expandedRuns, setExpandedRuns] = useState<Record<string, WorkflowRun[] | undefined>>({});
    const [showForm, setShowForm] = useState(false);

    const [formName, setFormName] = useState("");
    const [formDescription, setFormDescription] = useState("");
    const [formTrigger, setFormTrigger] = useState<WorkflowTriggerType>("lead_created");
    const [formConditions, setFormConditions] = useState<WorkflowCondition[]>([]);
    const [formActions, setFormActions] = useState<WorkflowAction[]>([emptyAction()]);
    const [formError, setFormError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);

    const load = useCallback(async () => {
        setError(null);
        try {
            const [wf, appr] = await Promise.all([listWorkflows(), listWorkflowApprovals()]);
            setWorkflows(wf);
            setApprovals(appr);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    function withBusy<T>(id: string, fn: () => Promise<T>): Promise<T> {
        setBusyIds((current) => new Set(current).add(id));
        return fn().finally(() => {
            setBusyIds((current) => {
                const next = new Set(current);
                next.delete(id);
                return next;
            });
        });
    }

    async function handleToggle(workflow: Workflow) {
        try {
            const updated = await withBusy(workflow.id, () =>
                workflow.status === "active" ? disableWorkflow(workflow.id) : enableWorkflow(workflow.id)
            );
            setWorkflows((current) => current?.map((w) => (w.id === workflow.id ? updated : w)) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    async function handleDelete(workflow: Workflow) {
        if (!window.confirm(`Delete "${workflow.name}"? This can't be undone.`)) return;
        const previous = workflows;
        setWorkflows((current) => current?.filter((w) => w.id !== workflow.id) ?? current);
        try {
            await withBusy(workflow.id, () => deleteWorkflow(workflow.id));
        } catch (err) {
            setWorkflows(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    async function handleToggleHistory(workflow: Workflow) {
        if (expandedRuns[workflow.id]) {
            setExpandedRuns((current) => ({ ...current, [workflow.id]: undefined }));
            return;
        }
        try {
            const runs = await listWorkflowRuns(workflow.id);
            setExpandedRuns((current) => ({ ...current, [workflow.id]: runs }));
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    async function handleDecideApproval(approval: ApprovalRequestOut, approve: boolean) {
        try {
            const updated = await withBusy(approval.id, () => decideWorkflowApproval(approval.id, approve));
            setApprovals((current) => current?.map((a) => (a.id === approval.id ? updated : a)) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    function applyTemplate(template: (typeof TEMPLATES)[number]) {
        setFormName(template.label.split(" → ")[0] ?? template.label);
        setFormDescription(template.description);
        setFormTrigger(template.trigger_type);
        setFormConditions(template.conditions);
        setFormActions(template.actions);
        setFormError(null);
        setShowForm(true);
    }

    function resetForm() {
        setFormName("");
        setFormDescription("");
        setFormTrigger("lead_created");
        setFormConditions([]);
        setFormActions([emptyAction()]);
        setFormError(null);
    }

    async function handleCreate(e: React.FormEvent) {
        e.preventDefault();
        setFormError(null);
        if (!formName.trim()) {
            setFormError("Give this workflow a name.");
            return;
        }
        setSaving(true);
        try {
            const created = await createWorkflow({
                name: formName.trim(),
                description: formDescription.trim() || null,
                trigger_type: formTrigger,
                conditions: formConditions,
                actions: formActions,
            });
            setWorkflows((current) => (current ? [created, ...current] : [created]));
            setShowForm(false);
            resetForm();
        } catch (err) {
            setFormError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    const pendingApprovals = (approvals ?? []).filter((a) => a.status === "pending");

    return (
        <AppShell>
            <PageHeader
                title="Workflows"
                description="Controlled automation: when something real happens (a new lead, a booked appointment, an escalated ticket), run deterministic, permission-aware actions - never an autonomous AI agent."
                actions={
                    <Button onClick={() => { resetForm(); setShowForm((v) => !v); }}>
                        <Plus size={16} aria-hidden="true" />
                        New workflow
                    </Button>
                }
            />

            {error && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50">
                    <p className="text-sm text-red-700">{error}</p>
                </Card>
            )}

            {pendingApprovals.length > 0 && (
                <Card className="p-4 mb-6 border-amber-200 bg-amber-50">
                    <h2 className="text-sm font-semibold text-amber-900 mb-3">
                        {pendingApprovals.length} action{pendingApprovals.length === 1 ? "" : "s"} awaiting your approval
                    </h2>
                    <ul className="space-y-2">
                        {pendingApprovals.map((approval) => (
                            <li key={approval.id} className="flex items-center justify-between gap-3 bg-white rounded-lg border border-amber-200 px-3 py-2">
                                <div className="min-w-0">
                                    <p className="text-sm text-slate-800 truncate">{approval.summary}</p>
                                    <p className="text-xs text-slate-400">{new Date(approval.created_at).toLocaleString()}</p>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                    <Button size="sm" onClick={() => handleDecideApproval(approval, true)} loading={busyIds.has(approval.id)}>
                                        <CheckCircle2 size={14} aria-hidden="true" />
                                        Approve
                                    </Button>
                                    <Button size="sm" variant="secondary" onClick={() => handleDecideApproval(approval, false)} disabled={busyIds.has(approval.id)}>
                                        <XCircle size={14} aria-hidden="true" />
                                        Reject
                                    </Button>
                                </div>
                            </li>
                        ))}
                    </ul>
                </Card>
            )}

            {showForm && (
                <Card className="p-5 mb-6">
                    <h2 className="text-sm font-semibold text-slate-800 mb-3">New workflow</h2>

                    <div className="mb-4">
                        <p className="text-xs font-medium text-slate-500 mb-2">Quick start templates</p>
                        <div className="flex flex-col gap-2">
                            {TEMPLATES.map((t) => (
                                <button
                                    key={t.label}
                                    type="button"
                                    onClick={() => applyTemplate(t)}
                                    className="text-left rounded-lg border border-slate-200 px-3 py-2 text-sm hover:border-brand-400 hover:bg-brand-50/40"
                                >
                                    <span className="font-medium text-slate-700">{t.label}</span>
                                    <span className="block text-xs text-slate-400 mt-0.5">{t.description}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    <form onSubmit={handleCreate} className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs font-medium text-slate-500 mb-1">Name</label>
                                <input
                                    value={formName}
                                    onChange={(e) => setFormName(e.target.value)}
                                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
                                    placeholder="e.g. Notify me on urgent support issues"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-slate-500 mb-1">Trigger</label>
                                <select
                                    value={formTrigger}
                                    onChange={(e) => {
                                        setFormTrigger(e.target.value as WorkflowTriggerType);
                                        setFormConditions([]);
                                    }}
                                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
                                >
                                    {Object.entries(TRIGGER_LABELS).map(([value, label]) => (
                                        <option key={value} value={value}>{label}</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">Description (optional)</label>
                            <input
                                value={formDescription}
                                onChange={(e) => setFormDescription(e.target.value)}
                                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
                            />
                        </div>

                        <div>
                            <div className="flex items-center justify-between mb-1.5">
                                <label className="text-xs font-medium text-slate-500">Conditions (all must be true - optional)</label>
                                <button
                                    type="button"
                                    className="text-xs text-brand-600 hover:underline"
                                    onClick={() => setFormConditions((c) => [...c, { field: TRIGGER_FIELDS[formTrigger][0], op: "is_set" }])}
                                >
                                    + Add condition
                                </button>
                            </div>
                            <div className="space-y-2">
                                {formConditions.map((cond, i) => (
                                    <div key={i} className="flex items-center gap-2">
                                        <select
                                            value={cond.field}
                                            onChange={(e) => setFormConditions((c) => c.map((x, xi) => (xi === i ? { ...x, field: e.target.value } : x)))}
                                            className="rounded-md border border-slate-300 text-xs px-2 py-1.5"
                                        >
                                            {TRIGGER_FIELDS[formTrigger].map((f) => <option key={f} value={f}>{f}</option>)}
                                        </select>
                                        <select
                                            value={cond.op}
                                            onChange={(e) => setFormConditions((c) => c.map((x, xi) => (xi === i ? { ...x, op: e.target.value as WorkflowCondition["op"] } : x)))}
                                            className="rounded-md border border-slate-300 text-xs px-2 py-1.5"
                                        >
                                            <option value="eq">equals</option>
                                            <option value="neq">does not equal</option>
                                            <option value="is_set">is set</option>
                                            <option value="is_not_set">is not set</option>
                                            <option value="contains">contains</option>
                                        </select>
                                        {cond.op !== "is_set" && cond.op !== "is_not_set" && (
                                            <input
                                                value={cond.value ?? ""}
                                                onChange={(e) => setFormConditions((c) => c.map((x, xi) => (xi === i ? { ...x, value: e.target.value } : x)))}
                                                placeholder="value"
                                                className="flex-1 rounded-md border border-slate-300 text-xs px-2 py-1.5"
                                            />
                                        )}
                                        <button type="button" onClick={() => setFormConditions((c) => c.filter((_, xi) => xi !== i))} className="text-slate-400 hover:text-red-600">
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div>
                            <div className="flex items-center justify-between mb-1.5">
                                <label className="text-xs font-medium text-slate-500">Actions</label>
                                <button type="button" className="text-xs text-brand-600 hover:underline" onClick={() => setFormActions((a) => [...a, emptyAction()])}>
                                    + Add action
                                </button>
                            </div>
                            <div className="space-y-3">
                                {formActions.map((action, i) => (
                                    <div key={i} className="rounded-lg border border-slate-200 p-3">
                                        <div className="flex items-center justify-between mb-2">
                                            <select
                                                value={action.type}
                                                onChange={(e) =>
                                                    setFormActions((a) => a.map((x, xi) => (xi === i ? { type: e.target.value as WorkflowAction["type"], config: {} } : x)))
                                                }
                                                className="rounded-md border border-slate-300 text-xs px-2 py-1.5"
                                            >
                                                {Object.entries(ACTION_LABELS).map(([value, label]) => (
                                                    <option key={value} value={value}>{label}</option>
                                                ))}
                                            </select>
                                            <button type="button" onClick={() => setFormActions((a) => a.filter((_, xi) => xi !== i))} className="text-slate-400 hover:text-red-600">
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                        <p className="text-xs text-slate-400">
                                            Use the Quick start templates above for a ready-to-edit example of this action's configuration.
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {formError && <p className="text-sm text-red-600">{formError}</p>}

                        <div className="flex items-center gap-2">
                            <Button type="submit" loading={saving}>Create workflow</Button>
                            <Button type="button" variant="secondary" onClick={() => { setShowForm(false); resetForm(); }}>Cancel</Button>
                        </div>
                    </form>
                </Card>
            )}

            <Card className="overflow-hidden">
                {workflows === null && !error && <LoadingState label="Loading workflows…" />}
                {workflows !== null && workflows.length === 0 && (
                    <EmptyState
                        icon={<WorkflowIcon size={32} />}
                        title="No workflows yet"
                        description="Use a quick start template above, or create your own: pick a trigger, add conditions, and choose what happens automatically."
                        action={<Button size="sm" onClick={() => setShowForm(true)}><Plus size={15} aria-hidden="true" />Create your first workflow</Button>}
                    />
                )}
                {workflows !== null && workflows.length > 0 && (
                    <ul className="divide-y divide-slate-100">
                        {workflows.map((workflow) => {
                            const isBusy = busyIds.has(workflow.id);
                            const runs = expandedRuns[workflow.id];
                            const isExpanded = runs !== undefined;
                            return (
                                <li key={workflow.id} className="p-4">
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="min-w-0">
                                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                <p className="text-sm font-medium text-slate-800">{workflow.name}</p>
                                                <Badge tone={STATUS_TONE[workflow.status]}>{workflow.status}</Badge>
                                            </div>
                                            <p className="text-xs text-slate-500 mb-1">{TRIGGER_LABELS[workflow.trigger_type]}</p>
                                            {workflow.description && <p className="text-xs text-slate-400">{workflow.description}</p>}
                                            <p className="text-xs text-slate-400 mt-1">
                                                {workflow.actions.length} action{workflow.actions.length === 1 ? "" : "s"}
                                                {workflow.conditions.length > 0 && ` · ${workflow.conditions.length} condition${workflow.conditions.length === 1 ? "" : "s"}`}
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-1 shrink-0">
                                            <button
                                                onClick={() => handleToggleHistory(workflow)}
                                                className="text-slate-400 hover:text-brand-600 p-1.5"
                                                title="View execution history"
                                            >
                                                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                            </button>
                                            <button
                                                onClick={() => handleToggle(workflow)}
                                                disabled={isBusy}
                                                className="text-slate-400 hover:text-brand-600 disabled:opacity-40 p-1.5"
                                                title={workflow.status === "active" ? "Disable" : "Enable"}
                                            >
                                                {isBusy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                                            </button>
                                            <button onClick={() => handleDelete(workflow)} disabled={isBusy} className="text-slate-400 hover:text-red-600 disabled:opacity-40 p-1.5">
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </div>

                                    {isExpanded && (
                                        <div className="mt-3 rounded-lg bg-slate-50 p-3">
                                            {runs && runs.length === 0 && <p className="text-xs text-slate-400">No runs yet.</p>}
                                            {runs && runs.length > 0 && (
                                                <ul className="space-y-2">
                                                    {runs.map((run) => (
                                                        <li key={run.id} className="text-xs">
                                                            <div className="flex items-center gap-2">
                                                                <Badge tone={RUN_STATUS_TONE[run.status]}>{run.status}</Badge>
                                                                <span className="text-slate-400">{run.started_at ? new Date(run.started_at).toLocaleString() : ""}</span>
                                                            </div>
                                                            {run.error && <p className="text-red-600 mt-0.5">{run.error}</p>}
                                                        </li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                )}
            </Card>
        </AppShell>
    );
}
