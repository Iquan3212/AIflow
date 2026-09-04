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