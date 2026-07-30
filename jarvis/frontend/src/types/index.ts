export interface Task {
  id: string;
  original_request: string;
  normalized_goal: string | null;
  state: TaskState;
  version: number;
  active_action_id: string | null;
  pending_question: string | null;
  final_result: string | null;
  created_at: string;
  updated_at: string;
  terminal_reason: string | null;
}

export type TaskState = 
  | 'created'
  | 'running'
  | 'waiting_for_user'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'interrupted';

export interface TaskEvent {
  id: number;
  task_id: string;
  event_type: string;
  event_data: Record<string, any>;
  sequence_num: number;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  database_connected: boolean;
  cloud_configured: boolean;
}

export interface ToolInfo {
  name: string;
  description: string;
}
