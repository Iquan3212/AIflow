import api from "./api";
import type { EmployeeInfo } from "../types/ai";

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

export async function setEmployeeEnabled(id: string, enabled: boolean): Promise<void> {
  await api.patch(`/workforce/${encodeURIComponent(id)}/enabled`, { enabled });
}

export async function updateEmployeeSettings(id: string, settings: Record<string, unknown>): Promise<void> {
  await api.patch(`/workforce/${encodeURIComponent(id)}/settings`, settings);
}