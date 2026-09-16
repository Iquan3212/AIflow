export type WorkflowStatus = "active" | "paused" | "disabled";

export type WorkflowTriggerType =
    | "lead_created"
    | "appointment_created"
    | "appointment_rescheduled"
    | "appointment_cancelled"
    | "support_escalated"
    // Phase 11: real-estate workflow triggers
    | "lead_status_changed"
    | "lead_qualified"
    | "appointment_confirmed"
    | "appointment_completed"
    | "appointment_no_show"
    | "booking_initiated"
    | "booking_confirmed"
    | "booking_cancelled"
    | "booking_completed";

export type WorkflowRunStatus = "pending" | "running" | "waiting_approval" | "succeeded" | "failed" | "cancelled";
export type WorkflowStepStatus = "pending" | "running" | "waiting_approval" | "succeeded" | "failed" | "skipped";
export type ApprovalRequestStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface WorkflowCondition {
    field: string;
    op: "eq" | "neq" | "is_set" | "is_not_set" | "contains";
    value?: string | null;
}

export interface WorkflowAction {
    type: "send_notification" | "create_gmail_draft" | "send_gmail" | "request_approval" | "run_ai_specialist";
    config: Record<string, unknown>;
    requires_approval?: boolean;
}

// Phase 11: the specialists run_ai_specialist may target - the same
// real-estate, tool-calling AI Workforce employees from Phase 10
// (backend: app.agents.manager_agent.SPECIALIST_ORDER).
export type AiSpecialist = "lead_qualifier" | "property_matcher" | "real_estate_sales" | "site_visit" | "customer_relations";

export const AI_SPECIALIST_LABELS: Record<AiSpecialist, string> = {
    lead_qualifier: "Lead Qualification AI",
    property_matcher: "Property Matching AI",
    real_estate_sales: "Real Estate Sales AI",
    site_visit: "Site Visit AI",
    customer_relations: "Customer Relations AI",
};

export interface Workflow {
    id: string;
    agency_id: string;
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
    agency_id: string;
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
    agency_id: string;
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
    lead_status_changed: "Lead status changed",
    lead_qualified: "Lead qualification score recorded",
    appointment_confirmed: "Site visit confirmed",
    appointment_completed: "Site visit completed",
    appointment_no_show: "Site visit no-show",
    booking_initiated: "Booking initiated",
    booking_confirmed: "Booking confirmed",
    booking_cancelled: "Booking cancelled",
    booking_completed: "Booking completed",
};

export const ACTION_LABELS: Record<WorkflowAction["type"], string> = {
    send_notification: "Send a notification",
    create_gmail_draft: "Create a Gmail draft",
    send_gmail: "Send a Gmail email",
    request_approval: "Request owner approval",
    run_ai_specialist: "Run an AI Workforce specialist",
};
