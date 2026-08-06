import api from "./api";

export interface LeadFunnel {
  stage: string;
  count: number;
}

export interface RevenueSummary {
  date: string;
  revenue: number;
}

export async function getLeadFunnel(): Promise<LeadFunnel[]> {
  const resp = await api.get("/analytics/lead-funnel");
  return resp.data;
}

export async function getAppointmentSummary(): Promise<{ date: string; count: number }[]> {
  const resp = await api.get("/analytics/appointments");
  return resp.data;
}

export async function getRevenueTrend(): Promise<RevenueSummary[]> {
  const resp = await api.get("/analytics/revenue");
  return resp.data;
}

export async function getAIUsage(): Promise<any> {
  const resp = await api.get("/analytics/ai-usage");
  return resp.data;
}

export async function getRecentActivity(): Promise<any[]> {
  const resp = await api.get("/analytics/recent-activity");
  return resp.data;
}