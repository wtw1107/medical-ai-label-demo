import type {
  LabelStudioStatusSyncResponse,
  PrelabelJobStatusResponse,
  PrelabelRunResponse,
  TaskImagesResponse,
} from "../types/api";
import { apiClient } from "./client";

export async function runPrelabel(taskId: string) {
  const response = await apiClient.post<PrelabelRunResponse>(`/api/tasks/${taskId}/prelabel`);
  return response.data;
}

export async function getPrelabelJob(jobId: string) {
  const response = await apiClient.get<PrelabelJobStatusResponse>(`/api/prelabel-jobs/${jobId}`);
  return response.data;
}

export async function getTaskImages(taskId: string) {
  const response = await apiClient.get<TaskImagesResponse>(`/api/tasks/${taskId}/images`);
  return response.data;
}

export async function syncLabelStudioStatus(taskId: string) {
  const response = await apiClient.post<LabelStudioStatusSyncResponse>(`/api/tasks/${taskId}/sync-label-studio-status`);
  return response.data;
}
