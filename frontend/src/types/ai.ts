export type EmployeeStatus = "online" | "offline" | "idle" | "busy" | "working" | "thinking";

export interface EmployeeInfo {
  id: string;
  name: string;
  avatar?: string;
  status: EmployeeStatus;
  online: boolean;
  current_task?: string;
  last_response?: string;
  tools: string[];
  confidence?: number; // 0..1
  memory_usage?: number; // percentage
  last_updated?: string; // ISO timestamp
}

export interface ConversationMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  agent?: string; // manager | sales | support | ...
  delegation?: {
    from: string;
    to: string;
    reason?: string;
  } | null;
  tool?: {
    name: string;
    status?: "success" | "error" | "pending";
    result?: unknown;
  } | null;
}

export interface Plan {
  intent: string;
  confidence: number;
  priority?: number;
  employees?: string[];
  tools?: string[];
}

export interface EmployeeResult {
  reply?: string;
  tool_result?: unknown;
  error?: string;
}

export interface ManagerResult {
  final_reply?: string;
  employee_results?: Record<string, EmployeeResult>;
  unified_context?: unknown;
}

export interface ManagerChatResponse {
  conversation_id: string;
  reply: string;
  intent: string;
  tool: string | null;
  confidence: number;
  plan?: Plan;
  manager_result?: ManagerResult;
}