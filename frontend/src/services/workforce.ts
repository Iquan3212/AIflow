import api from "./api";
import type { AIActionApprovalOut, EmployeeInfo } from "../types/ai";

export interface WorkforceResponse {
  employees: EmployeeInfo[];
  stats?: {
    total?: number;
    online?: number;
    busy?: number;
  };
}

export async function getWorkforce(): Promise<WorkforceResponse> {
  const resp = await api.get("/workforce");
  return resp.data as WorkforceResponse;
}

export async function getEmployee(id: string): Promise<EmployeeInfo> {
  const resp = await api.get(`/workforce/${encodeURIComponent(id)}`);
  return resp.data as EmployeeInfo;
}

// Phase 10C: the minimal AI-action approval inbox.
export async function listAIApprovals(): Promise<AIActionApprovalOut[]> {
  const resp = await api.get<AIActionApprovalOut[]>("/ai-approvals", { params: { pending_only: true } });
  return resp.data;
}

export async function decideAIApproval(id: string, approve: boolean): Promise<AIActionApprovalOut> {
  const resp = await api.post<AIActionApprovalOut>(`/ai-approvals/${id}/decide`, { approve });
  return resp.data;
}