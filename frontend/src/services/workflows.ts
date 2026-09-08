import api from "./api";
import type { ApprovalRequestOut, Workflow, WorkflowAction, WorkflowCondition, WorkflowRun, WorkflowTriggerType } from "../types/workflow";

export async function listWorkflows(): Promise<Workflow[]> {
    const response = await api.get<Workflow[]>("/workflows");
    return response.data;
}

export async function createWorkflow(payload: {
    name: string;
    description?: string | null;
    trigger_type: WorkflowTriggerType;
    conditions: WorkflowCondition[];
    actions: WorkflowAction[];
}): Promise<Workflow> {
    const response = await api.post<Workflow>("/workflows", payload);
    return response.data;
}

export async function updateWorkflow(
    id: string,
    payload: Partial<{ name: string; description: string | null; conditions: WorkflowCondition[]; actions: WorkflowAction[] }>
): Promise<Workflow> {
    const response = await api.put<Workflow>(`/workflows/${id}`, payload);
    return response.data;
}

export async function deleteWorkflow(id: string): Promise<void> {
    await api.delete(`/workflows/${id}`);
}

export async function enableWorkflow(id: string): Promise<Workflow> {
    const response = await api.post<Workflow>(`/workflows/${id}/enable`);
    return response.data;
}

export async function disableWorkflow(id: string): Promise<Workflow> {
    const response = await api.post<Workflow>(`/workflows/${id}/disable`);
    return response.data;
}

export async function listWorkflowRuns(workflowId: string): Promise<WorkflowRun[]> {
    const response = await api.get<WorkflowRun[]>(`/workflows/${workflowId}/runs`);
    return response.data;
}

export async function listWorkflowApprovals(): Promise<ApprovalRequestOut[]> {
    const response = await api.get<ApprovalRequestOut[]>("/workflow-approvals");
    return response.data;
}

export async function decideWorkflowApproval(id: string, approve: boolean): Promise<ApprovalRequestOut> {
    const response = await api.post<ApprovalRequestOut>(`/workflow-approvals/${id}/decide`, { approve });
    return response.data;
}
