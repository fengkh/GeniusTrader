import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  ApiMessage,
  Page,
  ResearchTask,
  ResearchTaskPayload,
  ResearchTaskPriority,
  ResearchTaskSourceType,
  ResearchTaskStatus,
  ResearchTaskStatusPayload,
  ResearchTaskType,
  UUID
} from "@/lib/api/types";

export interface ResearchTaskListParams {
  task_type?: ResearchTaskType | "";
  status?: ResearchTaskStatus | "";
  priority?: ResearchTaskPriority | "";
  stock_id?: UUID | "";
  due_date?: string;
  source_type?: ResearchTaskSourceType | "";
  open_only?: boolean;
  q?: string;
  limit?: number;
  offset?: number;
}

export async function listResearchTasks(
  params: ResearchTaskListParams = {}
): Promise<Page<ResearchTask>> {
  return apiRequest<Page<ResearchTask>>(
    `/research-tasks${toQueryString({
      task_type: params.task_type,
      status: params.status,
      priority: params.priority,
      stock_id: params.stock_id,
      due_date: params.due_date,
      source_type: params.source_type,
      open_only: params.open_only,
      q: params.q,
      limit: params.limit ?? 30,
      offset: params.offset ?? 0
    })}`
  );
}

export async function createResearchTask(payload: ResearchTaskPayload): Promise<ResearchTask> {
  return apiRequest<ResearchTask>("/research-tasks", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateResearchTaskStatus(
  taskId: UUID,
  payload: ResearchTaskStatusPayload
): Promise<ResearchTask> {
  return apiRequest<ResearchTask>(`/research-tasks/${taskId}/status`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function addResearchTaskUpdate(
  taskId: UUID,
  payload: {
    note: string;
    evidence_information_item_id?: UUID | null;
    evidence_analysis_version_id?: UUID | null;
    evidence_daily_review_version_id?: UUID | null;
  }
): Promise<ResearchTask> {
  return apiRequest<ResearchTask>(`/research-tasks/${taskId}/updates`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function dismissResearchTask(taskId: UUID): Promise<void> {
  await apiRequest<ApiMessage>(`/research-tasks/${taskId}`, {
    method: "DELETE"
  });
}
