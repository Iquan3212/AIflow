export type WorkflowStatus = "active" | "paused" | "disabled";

export type WorkflowTriggerType =
    | "lead_created"
    | "appointment_created"
    | "appointment_rescheduled"
    | "appointment_cancelled"
    | "support_escalated";

export type WorkflowRunStatus = "pending" | "running" | "waiting_approval" | "succeeded" | "failed" | "cancelled";
export type WorkflowStepStatus = "pending" | "running" | "waiting_approval" | "succeeded" | "failed" | "skipped";
export type ApprovalRequestStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface WorkflowCondition {
    field: string;
    op: "eq" | "neq" | "is_set" | "is_not_set" | "contains";
    value?: string | null;
}

export interface WorkflowAction {
    type: "send_notification" | "create_gmail_draft" | "send_gmail" | "request_approval";
    config: Record<string, unknown>;
    requires_approval?: boolean;
}

export interface Workflow {
    id: string;
    business_id: string;
    name: string;
    description: string | null;
    status: WorkflowStatus;
    trigger_type: WorkflowTriggerType;
    conditions: WorkflowCondition[];
    actions: WorkflowAction[];
    created_at: string;
    updated_at: string;
}

export interface WorkflowStepRun {
    id: string;
    step_index: number;
    action_type: string;
    status: WorkflowStepStatus;
    input: Record<string, unknown> | null;
    result: Record<string, unknown> | null;
    error: string | null;
    approval_request_id: string | null;
    gmail_pending_action_id: string | null;
    started_at: string | null;
    completed_at: string | null;
}

export interface WorkflowRun {
    id: string;
    workflow_id: string;
    business_id: string;
    status: WorkflowRunStatus;
    trigger_event_id: string;
    trigger_data: Record<string, unknown>;
    started_at: string | null;
    completed_at: string | null;
    error: string | null;
    steps: WorkflowStepRun[];
}

export interface ApprovalRequestOut {
    id: string;
    business_id: string;
    workflow_step_run_id: string;
    action_type: string;
    summary: string;
    status: ApprovalRequestStatus;
    created_at: string;
    decided_at: string | null;
}

export const TRIGGER_LABELS: Record<WorkflowTriggerType, string> = {
    lead_created: "New lead created",
    appointment_created: "Appointment booked",
    appointment_rescheduled: "Appointment rescheduled",
    appointment_cancelled: "Appointment cancelled",
    support_escalated: "Support ticket escalated (high priority)",
};

export const ACTION_LABELS: Record<WorkflowAction["type"], string> = {
    send_notification: "Send a notification",
    create_gmail_draft: "Create a Gmail draft",
    send_gmail: "Send a Gmail email",
    request_approval: "Request owner approval",
};
