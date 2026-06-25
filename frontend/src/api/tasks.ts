import type {
  AnnotationTaskCreatePayload,
  AnnotationTaskCreateResponse,
  AnnotationTaskDetail,
  AnnotationTaskListResponse,
  LabelStudioUrlResponse,
} from "../types/api";
import { apiClient } from "./client";

export async function listTasks() {
  const response = await apiClient.get<AnnotationTaskListResponse>("/api/tasks");
  return response.data;
}

export async function createTask(payload: AnnotationTaskCreatePayload) {
  const response = await apiClient.post<AnnotationTaskCreateResponse>("/api/tasks", payload);
  return response.data;
}

export async function getTaskDetail(taskId: string) {
  const response = await apiClient.get<AnnotationTaskDetail>(`/api/tasks/${taskId}`);
  return response.data;
}

export async function getLabelStudioUrl(taskId: string) {
  const response = await apiClient.get<LabelStudioUrlResponse>(`/api/tasks/${taskId}/label-studio-url`);
  return response.data;
}
